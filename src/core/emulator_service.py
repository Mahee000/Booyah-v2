import subprocess
import os
import io
import shutil
import logging
from typing import List, Dict, Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

class EmulatorService:
    def __init__(self, adb_path: Optional[str] = None):
        self.adb_path = adb_path or self.find_best_adb()
        self._ensure_server()

    @staticmethod
    def find_best_adb() -> str:
        """
        Uses standard Android Platform-Tools ADB (version 1.0.41) or system adb.
        """
        sys_adb = shutil.which("adb")
        if sys_adb:
            return sys_adb

        candidates = [
            r"C:\Users\nayee\AppData\Local\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe",
            r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
            r"C:\leidian\LDPlayer9\adb.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "adb"

    def _ensure_server(self):
        try:
            subprocess.run([self.adb_path, "start-server"], capture_output=True, timeout=10)
        except Exception as e:
            logger.error(f"Error starting ADB server: {e}")

    def connect_device(self, address: str) -> Tuple[bool, str]:
        """
        Manually connects to an emulator or device via IP:Port or Port (e.g., '127.0.0.1:5555' or '5555').
        """
        addr = address.strip()
        if not addr:
            return False, "Address cannot be empty"
        if ":" not in addr and addr.isdigit():
            addr = f"127.0.0.1:{addr}"
        try:
            res = subprocess.run(
                [self.adb_path, "connect", addr],
                capture_output=True,
                text=True,
                timeout=8
            )
            out = (res.stdout + " " + res.stderr).strip()
            if "connected to" in out.lower() or "already connected" in out.lower():
                return True, out
            return False, out if out else f"Failed to connect to {addr}"
        except Exception as e:
            logger.error(f"Manual connect to {addr} failed: {e}")
            return False, str(e)

    def get_connected_devices(self) -> List[Dict[str, str]]:
        """
        Discovers all connected emulators using the exact Booyah port mapping:
        - Maps emulator-XXXX (console port XXXX) to adb port (XXXX + 1).
        - Maps TCP tunnel 127.0.0.1:YYYY directly to adb port YYYY.
        - Deduplicates identical instances while cleanly preserving standalone
          instances (e.g. 127.0.0.1:5595).
        """
        try:
            proc = subprocess.run(
                [self.adb_path, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = proc.stdout.strip().split("\n")[1:]
            raw_devices = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    serial = parts[0]
                    state = parts[1]
                    if state.lower() == "offline":
                        continue

                    model = "Android Emulator"
                    for p in parts[2:]:
                        if p.startswith("model:"):
                            model = p.split(":", 1)[1]
                        elif p.startswith("device:") and model == "Android Emulator":
                            model = p.split(":", 1)[1]

                    raw_devices.append({
                        "serial": serial,
                        "state": state,
                        "model": model
                    })

            # Sort so emulator-XXXX is processed first or TCP is prioritized consistently
            raw_devices.sort(key=lambda d: (0 if d["serial"].startswith("emulator-") else 1, d["serial"]))

            unique_devices = []
            seen_ports = set()

            for d in raw_devices:
                serial = d["serial"]
                port = None
                if ":" in serial:
                    try:
                        port = int(serial.split(":")[1])
                    except ValueError:
                        pass
                elif serial.startswith("emulator-"):
                    try:
                        base = int(serial.split("-")[1])
                        port = base + 1  # e.g. emulator-5554 -> adb port 5555
                    except ValueError:
                        pass

                if port is not None:
                    if port in seen_ports:
                        continue
                    seen_ports.add(port)

                unique_devices.append(d)

            return sorted(unique_devices, key=lambda x: x["serial"])
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return []

    def capture_screenshot(self, serial: str) -> Optional[Image.Image]:
        """Captures frame directly from emulator via screencap"""
        try:
            proc = subprocess.run(
                [self.adb_path, "-s", serial, "exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=6
            )
            data = proc.stdout
            if proc.returncode == 0 and len(data) > 1000:
                if b"\r\r\n" in data[:100]:
                    data = data.replace(b"\r\r\n", b"\n")
                elif b"\r\n" in data[:100] and not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    data = data.replace(b"\r\n", b"\n")

                img = Image.open(io.BytesIO(data))
                return img.convert("RGB")
        except Exception as e:
            logger.error(f"Screenshot failed on {serial}: {e}")
        return None

    def capture_frame(self, serial: str) -> Optional[Image.Image]:
        """Alias for capture_screenshot"""
        return self.capture_screenshot(serial)

    def get_screen_size(self, serial: str) -> Tuple[int, int]:
        """Returns emulator screen resolution (width, height), normalized for landscape gaming"""
        try:
            proc = subprocess.run(
                [self.adb_path, "-s", serial, "shell", "wm", "size"],
                capture_output=True, text=True, timeout=4
            )
            for line in proc.stdout.splitlines():
                if "Physical size:" in line:
                    parts = line.split(":")[-1].strip().split("x")
                    dim1, dim2 = int(parts[0]), int(parts[1])
                    # Free Fire runs in landscape mode (width > height)
                    w = max(dim1, dim2)
                    h = min(dim1, dim2)
                    return w, h
        except Exception as e:
            logger.error(f"Failed to get screen size for {serial}: {e}")
        return 1600, 900

    def tap(self, serial: str, x: int, y: int) -> bool:
        """Taps screen at absolute pixel coordinates (x, y)"""
        try:
            subprocess.run(
                [self.adb_path, "-s", serial, "shell", "input", "tap", str(x), str(y)],
                capture_output=True, timeout=4
            )
            return True
        except Exception as e:
            logger.error(f"Tap failed on {serial} at ({x}, {y}): {e}")
            return False

    def tap_normalized(self, serial: str, norm_x: float, norm_y: float) -> bool:
        """Taps screen using percentage/normalized coordinates (0.0 to 1.0)"""
        w, h = self.get_screen_size(serial)
        abs_x = int(norm_x * w)
        abs_y = int(norm_y * h)
        return self.tap(serial, abs_x, abs_y)

    def swipe(self, serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> bool:
        """Swipes screen from (x1, y1) to (x2, y2) over duration_ms milliseconds"""
        try:
            subprocess.run(
                [self.adb_path, "-s", serial, "shell", "input", "swipe",
                 str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
                capture_output=True, timeout=5
            )
            return True
        except Exception as e:
            logger.error(f"Swipe failed on {serial} from ({x1}, {y1}) to ({x2}, {y2}): {e}")
            return False

    def swipe_normalized(self, serial: str, nx1: float, ny1: float, nx2: float, ny2: float, duration_ms: int = 400) -> bool:
        """Swipes screen using normalized coordinates (0.0 to 1.0)"""
        w, h = self.get_screen_size(serial)
        x1 = int(nx1 * w)
        y1 = int(ny1 * h)
        x2 = int(nx2 * w)
        y2 = int(ny2 * h)
        return self.swipe(serial, x1, y1, x2, y2, duration_ms)

    def input_text(self, serial: str, text: str) -> bool:
        """Types alphanumeric text on emulator (spaces converted to %s)"""
        try:
            escaped = str(text).replace(" ", "%s").replace("'", "\\'")
            subprocess.run(
                [self.adb_path, "-s", serial, "shell", "input", "text", escaped],
                capture_output=True, timeout=5
            )
            return True
        except Exception as e:
            logger.error(f"Input text failed on {serial}: {e}")
            return False


