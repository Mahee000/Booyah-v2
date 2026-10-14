import os
import json
import time
import math
import logging
import requests
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRESETS_CACHE_FILE = os.path.join(WORKSPACE_DIR, "presets_cache.json")
SUPABASE_URL = "https://akudigcrinflfhnnqzbu.supabase.co/functions/v1/get-presets"
APP_SECRET = "BOOYAH_CLIENT_SECURE_TOKEN_2026"

# 3 Primary Game Modes
MODES = [
    {"id": "BR", "name": "Battle Royale (BR)"},
    {"id": "CS", "name": "Clash Squad (CS)"},
    {"id": "LW", "name": "Lone Wolf (LW)"},
]

# Keys explicitly removed per user instruction:
# 1. Esports Score Parsing (esportsMode, esportsKillPoints, esportsPlacementPoints)
# 2. Auto Room Creation Macro (autoRoomCreation, autoHostActions, autoHostMode, autoHostClickX, autoHostClickY)
# 5. Master/Client Sync & Rewards (autoRewards, autoRewardsMode)
# 7. Auto Close Room Delay (room_close_delay)
KEYS_TO_REMOVE = {
    "esportsMode", "esportsKillPoints", "esportsPlacementPoints",
    "autoRoomCreation", "autoHostActions", "autoHostMode", "autoHostClickX", "autoHostClickY",
    "autoRewards", "autoRewardsMode",
    "room_close_delay",
    # Old hardcoded click targets (replaced by unified standard coordinates)
    "clickX", "clickY", "clickDelay"
}

# Standard 11-step Lone Wolf Auto Room Creation macro sequence calibrated for Free Fire
LONE_WOLF_ROOM_CREATION_STEPS = [
    {"type": "click", "delay": 1.0, "x": 0.829, "y": 0.835},
    {"type": "click", "delay": 1.0, "x": 0.516, "y": 0.895},
    {"type": "click", "delay": 1.0, "x": 0.891, "y": 0.877},
    {"type": "click", "delay": 1.0, "x": 0.756, "y": 0.348},
    {"type": "click", "delay": 1.0, "x": 0.377, "y": 0.578},
    {"type": "click", "delay": 1.0, "x": 0.039, "y": 0.296},
    {"type": "click", "delay": 1.0, "x": 0.462, "y": 0.212},
    {"type": "click", "delay": 1.0, "x": 0.491, "y": 0.848},
    {"type": "click", "delay": 1.0, "x": 0.509, "y": 0.757},
    {"type": "click", "delay": 1.0, "x": 0.481, "y": 0.512},
    {"type": "click", "delay": 1.0, "x": 0.610, "y": 0.628}
]

# Standard 11-step Clash Squad Auto Room Creation macro sequence calibrated for Free Fire
CLASH_SQUAD_ROOM_CREATION_STEPS = [
    {"type": "click", "delay": 1.0, "x": 0.829, "y": 0.835},
    {"type": "click", "delay": 1.0, "x": 0.516, "y": 0.895},
    {"type": "click", "delay": 1.0, "x": 0.891, "y": 0.877},
    {"type": "click", "delay": 1.0, "x": 0.756, "y": 0.348},
    {"type": "click", "delay": 1.0, "x": 0.378, "y": 0.418},
    {"type": "click", "delay": 1.0, "x": 0.039, "y": 0.296},
    {"type": "click", "delay": 1.0, "x": 0.462, "y": 0.212},
    {"type": "click", "delay": 1.0, "x": 0.491, "y": 0.848},
    {"type": "click", "delay": 1.0, "x": 0.509, "y": 0.757},
    {"type": "click", "delay": 1.0, "x": 0.481, "y": 0.512},
    {"type": "click", "delay": 1.0, "x": 0.610, "y": 0.628}
]

# Standard 11-step Battle Royale Auto Room Creation macro sequence calibrated for Free Fire
BATTLE_ROYALE_ROOM_CREATION_STEPS = [
    {"type": "click", "delay": 1.0, "x": 0.829, "y": 0.835},
    {"type": "click", "delay": 1.0, "x": 0.516, "y": 0.895},
    {"type": "click", "delay": 1.0, "x": 0.891, "y": 0.877},
    {"type": "click", "delay": 1.0, "x": 0.756, "y": 0.348},
    {"type": "click", "delay": 1.0, "x": 0.367, "y": 0.473},
    {"type": "click", "delay": 1.0, "x": 0.039, "y": 0.296},
    {"type": "click", "delay": 1.0, "x": 0.462, "y": 0.212},
    {"type": "click", "delay": 1.0, "x": 0.491, "y": 0.848},
    {"type": "click", "delay": 1.0, "x": 0.509, "y": 0.757},
    {"type": "click", "delay": 1.0, "x": 0.481, "y": 0.512},
    {"type": "click", "delay": 1.0, "x": 0.610, "y": 0.628}
]

# Mode-level default Room Creation Macros (Applies to all current & future presets of that mode)
MODE_DEFAULT_ACTIONS: Dict[str, List[Dict[str, Any]]] = {
    "LW": LONE_WOLF_ROOM_CREATION_STEPS,
    "CS": CLASH_SQUAD_ROOM_CREATION_STEPS,
    "BR": BATTLE_ROYALE_ROOM_CREATION_STEPS
}

def get_default_room_actions_for_mode(mode: str) -> List[Dict[str, Any]]:
    """Returns the default room creation macro sequence for a game mode (e.g., Lone Wolf)."""
    import copy
    steps = MODE_DEFAULT_ACTIONS.get(mode.upper(), [])
    return copy.deepcopy(steps)

# Clean built-in fallback presets with 4 (crop regions), 6 (sleepTime), and 8 (logInterval) implemented
DEFAULT_PRESETS = {
    # BR Presets
    "br_solo": {
        "id": "br_solo",
        "mode": "BR",
        "name": "Battle Royale Solo",
        "order": 0,
        "cropX": 0.03,
        "cropY": 0.22,
        "cropW": 0.93,
        "cropH": 0.66,
        "sleepTime": 20,
        "logInterval": 30,
        "autoHostActions": BATTLE_ROYALE_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1524848505682923562/Gk5qks0oYLhhXQUvqXM4zmo1Tcik00DH4uJerCcl66n_WRyXBrR2Iu95h3ZIf26S3ezX"
    },
    "br_duo": {
        "id": "br_duo",
        "mode": "BR",
        "name": "Battle Royale Duo",
        "order": 1,
        "cropX": 0.03,
        "cropY": 0.22,
        "cropW": 0.93,
        "cropH": 0.66,
        "sleepTime": 20,
        "logInterval": 30,
        "autoHostActions": BATTLE_ROYALE_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1504582155693719695/oFxLANUuiR7KU5bKexKFYv8oOGhXN3qHVc_1O5W2_qNdUv_WZtF4Qp0fNEONAxiHsMTK"
    },
    "br_squad": {
        "id": "br_squad",
        "mode": "BR",
        "name": "Battle Royale Squad",
        "order": 2,
        "cropX": 0.03,
        "cropY": 0.22,
        "cropW": 0.93,
        "cropH": 0.66,
        "sleepTime": 20,
        "logInterval": 30,
        "autoHostActions": BATTLE_ROYALE_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1504582155693719695/oFxLANUuiR7KU5bKexKFYv8oOGhXN3qHVc_1O5W2_qNdUv_WZtF4Qp0fNEONAxiHsMTK"
    },
    "br_pro_league": {
        "id": "br_pro_league",
        "mode": "BR",
        "name": "Battle Royale Pro League",
        "order": 3,
        "cropX": 0.03,
        "cropY": 0.22,
        "cropW": 0.93,
        "cropH": 0.66,
        "sleepTime": 20,
        "logInterval": 30,
        "autoHostActions": BATTLE_ROYALE_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1504582155693719695/oFxLANUuiR7KU5bKexKFYv8oOGhXN3qHVc_1O5W2_qNdUv_WZtF4Qp0fNEONAxiHsMTK"
    },
    # CS Presets
    "std_cs": {
        "id": "std_cs",
        "mode": "CS",
        "name": "Standard Clash Squad",
        "order": 4,
        "cropX": 0.00,
        "cropY": 0.30,
        "cropW": 1.00,
        "cropH": 0.50,
        "sleepTime": 5,
        "logInterval": 20,
        "autoHostActions": CLASH_SQUAD_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1499045182522527865/sXgJ1eTPvF6ZC-5OEHvwVLduGYf_r8Q702yHx7dpuKphQ4Vfc-q7hDRyrKN4UILd7UMe"
    },
    "hs_cs": {
        "id": "hs_cs",
        "mode": "CS",
        "name": "HS Only Clash Squad",
        "order": 5,
        "cropX": 0.00,
        "cropY": 0.30,
        "cropW": 1.00,
        "cropH": 0.50,
        "sleepTime": 5,
        "logInterval": 20,
        "autoHostActions": CLASH_SQUAD_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1499045182522527865/sXgJ1eTPvF6ZC-5OEHvwVLduGYf_r8Q702yHx7dpuKphQ4Vfc-q7hDRyrKN4UILd7UMe"
    },
    # LW Presets
    "std_lw": {
        "id": "std_lw",
        "mode": "LW",
        "name": "Standard Lone Wolf",
        "order": 6,
        "cropX": 0.02,
        "cropY": 0.20,
        "cropW": 0.54,
        "cropH": 0.26,
        "sleepTime": 2,
        "logInterval": 15,
        "autoHostActions": LONE_WOLF_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1496127810979500186/lc5Vfn37uFuGd8c0G1y6X7_xemEBymesVII1vwa0sVGLhlhiZ4BKNv_CQoVvqzYEknbC"
    },
    "hs_lw": {
        "id": "hs_lw",
        "mode": "LW",
        "name": "HS Only Lone Wolf",
        "order": 7,
        "cropX": 0.02,
        "cropY": 0.20,
        "cropW": 0.54,
        "cropH": 0.26,
        "sleepTime": 2,
        "logInterval": 15,
        "autoHostActions": LONE_WOLF_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1500151388791898132/C51GZCSx2oxk9FaONO0O1voBk0tK_4Jk1enxFxFXLJRbjqAWtYYk4K8S5wflBfmodVJR"
    },
    "ltw_lw": {
        "id": "ltw_lw",
        "mode": "LW",
        "name": "LTW Lone Wolf",
        "order": 8,
        "cropX": 0.02,
        "cropY": 0.20,
        "cropW": 0.54,
        "cropH": 0.26,
        "sleepTime": 1,
        "logInterval": 10,
        "autoHostActions": LONE_WOLF_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1501542247915589734/5TfNK9F8wweL0KfR8L6xJYXo8CB6NdQBwc3SskJ9Y3_cwqE4s43v8-JvaPrqjvZAB2Uj"
    },
    "ltw_lw_2": {
        "id": "ltw_lw_2",
        "mode": "LW",
        "name": "LTW Lone Wolf 2",
        "order": 9,
        "cropX": 0.02,
        "cropY": 0.20,
        "cropW": 0.54,
        "cropH": 0.26,
        "sleepTime": 1,
        "logInterval": 10,
        "autoHostActions": LONE_WOLF_ROOM_CREATION_STEPS,
        "webhook": "https://ptb.discord.com/api/webhooks/1501542247915589734/5TfNK9F8wweL0KfR8L6xJYXo8CB6NdQBwc3SskJ9Y3_cwqE4s43v8-JvaPrqjvZAB2Uj"
    }
}

class PresetService:
    _presets: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_presets(cls) -> Dict[str, Dict[str, Any]]:
        """Loads presets from local cache or fetches directly from Supabase database"""
        if cls._presets:
            return cls._presets

        # 1. Try local cache first
        if os.path.exists(PRESETS_CACHE_FILE):
            try:
                with open(PRESETS_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if cached:
                        # Ensure autoHostActions is present for all presets
                        for key, p in cached.items():
                            mode = p.get("mode", "BR")
                            if not p.get("autoHostActions"):
                                p["autoHostActions"] = get_default_room_actions_for_mode(mode)
                        cls._presets = cached
                        return cls._presets
            except Exception:
                pass

        # 2. Fetch from Supabase
        fetched = cls.fetch_remote_presets()
        if fetched:
            for key, p in fetched.items():
                mode = p.get("mode", "BR")
                if not p.get("autoHostActions"):
                    p["autoHostActions"] = get_default_room_actions_for_mode(mode)
            cls._presets = fetched
            cls.save_cache(fetched)
        else:
            cls._presets = DEFAULT_PRESETS
            cls.save_cache(DEFAULT_PRESETS)

        return cls._presets

    @classmethod
    def fetch_remote_presets(cls) -> Optional[Dict[str, Dict[str, Any]]]:
        try:
            r = requests.post(
                SUPABASE_URL,
                headers={"x-app-secret": APP_SECRET},
                timeout=4
            )
            if r.status_code == 200:
                raw_data = r.json()
                parsed = {}
                for key, p in raw_data.items():
                    mode = p.get("mode", "BR").upper()
                    name = p.get("customName") or key
                    order = p.get("order_index", 99)

                    # Normalize crop values (some presets in DB use 0-100 integers, others 0.0-1.0 floats)
                    cx = float(p.get("cropX", 0.0))
                    cy = float(p.get("cropY", 0.0))
                    cw = float(p.get("cropW", 1.0))
                    ch = float(p.get("cropH", 1.0))
                    if cx > 1.0 or cy > 1.0 or cw > 1.0 or ch > 1.0:
                        cx /= 100.0
                        cy /= 100.0
                        cw /= 100.0
                        ch /= 100.0

                    # Filter out keys 1, 2, 3, 5, 7 from raw config
                    cleaned_cfg = {k: v for k, v in p.items() if k not in KEYS_TO_REMOVE}

                    c2x = float(p.get("crop2X", cx))
                    c2y = float(p.get("crop2Y", cy))
                    c2w = float(p.get("crop2W", cw))
                    c2h = float(p.get("crop2H", ch))
                    if c2x > 1.0 or c2y > 1.0 or c2w > 1.0 or c2h > 1.0:
                        c2x /= 100.0
                        c2y /= 100.0
                        c2w /= 100.0
                        c2h /= 100.0

                    parsed[key] = {
                        "id": key,
                        "mode": mode,
                        "name": name,
                        "order": order,
                        "webhook": p.get("webhook", ""),
                        # 4. Crop Regions
                        "cropX": max(0.0, min(1.0, cx)),
                        "cropY": max(0.0, min(1.0, cy)),
                        "cropW": max(0.1, min(1.0, cw)),
                        "cropH": max(0.1, min(1.0, ch)),
                        # Multi-page Scroll Crop Regions
                        "scrollCount": max(0, int(float(p.get("scrollCount", 0)))),
                        "crop2X": max(0.0, min(1.0, c2x)),
                        "crop2Y": max(0.0, min(1.0, c2y)),
                        "crop2W": max(0.1, min(1.0, c2w)),
                        "crop2H": max(0.1, min(1.0, c2h)),
                        # 6. Sleep time (minutes to pause after match)
                        "sleepTime": max(1, int(float(p.get("sleepTime", 5)))),
                        # 8. Log interval & offset (minutes / seconds for log cadence and match time rounding)
                        "logInterval": max(5, int(float(p.get("logInterval", 15)))),
                        "logOffset": int(float(p.get("logOffset", 0))),
                        # Inherit mode-level default Room Creation actions (e.g., Lone Wolf)
                        "autoHostActions": p.get("autoHostActions") or get_default_room_actions_for_mode(mode),
                        "config": cleaned_cfg
                    }
                return parsed
        except Exception as e:
            logger.warning(f"Could not fetch presets from database: {e}")
        return None

    @classmethod
    def save_cache(cls, data: Dict[str, Any]):
        try:
            with open(PRESETS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @classmethod
    def get_presets_for_mode(cls, mode_id: str) -> List[Dict[str, Any]]:
        """Returns sorted presets matching the given mode (BR, CS, or LW)"""
        all_presets = cls.load_presets()
        matching = [p for p in all_presets.values() if p.get("mode") == mode_id]
        return sorted(matching, key=lambda x: x.get("order", 99))

def get_rounded_time(timestamp_sec: float, interval_minutes: int, offset_minutes: int = 0) -> str:
    """
    Rounds a timestamp to the nearest match slot based on logInterval and logOffset,
    matching the exact legacy Booyah tournament match scheduling algorithm.
    e.g. interval=20m, offset=0 -> 2:00 PM, 2:20 PM, 2:40 PM.
    """
    interval_m = max(1, int(interval_minutes))
    offset_m = int(offset_minutes)

    ms = timestamp_sec * 1000.0
    interval_ms = interval_m * 60.0 * 1000.0
    offset_ms = offset_m * 60.0 * 1000.0

    # Local timezone adjustment
    local_time = time.localtime(timestamp_sec)
    tz_offset_sec = -(time.timezone if (local_time.tm_isdst == 0) else time.altzone)
    tz_offset_ms = tz_offset_sec * 1000.0

    local_ms = ms + tz_offset_ms
    rounded_local_ms = (math.floor((local_ms - offset_ms) / interval_ms) * interval_ms) + offset_ms
    rounded_utc_sec = (rounded_local_ms - tz_offset_ms) / 1000.0

    rounded_struct = time.localtime(rounded_utc_sec)
    hour = rounded_struct.tm_hour % 12
    if hour == 0:
        hour = 12
    ampm = "PM" if rounded_struct.tm_hour >= 12 else "AM"
    minute_str = f"{rounded_struct.tm_min:02d}"
    return f"{hour}:{minute_str} {ampm}"

def get_next_match_time_sec(now_sec: float, interval_minutes: int, offset_minutes: int = 0) -> float:
    """
    Computes the timestamp (in epoch seconds) of the upcoming scheduled match,
    aligned to tournament interval and offset.
    """
    interval_m = max(1, int(interval_minutes))
    offset_m = int(offset_minutes)

    ms = now_sec * 1000.0
    interval_ms = interval_m * 60.0 * 1000.0
    offset_ms = offset_m * 60.0 * 1000.0

    local_time = time.localtime(now_sec)
    tz_offset_sec = -(time.timezone if (local_time.tm_isdst == 0) else time.altzone)
    tz_offset_ms = tz_offset_sec * 1000.0

    local_ms = ms + tz_offset_ms
    current_match_local_ms = (math.floor((local_ms - offset_ms) / interval_ms) * interval_ms) + offset_ms
    next_match_local_ms = current_match_local_ms + interval_ms
    next_match_utc_sec = (next_match_local_ms - tz_offset_ms) / 1000.0

    return next_match_utc_sec

