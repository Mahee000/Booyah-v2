import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CLIENT_ID = "1522650316980355132"

class DiscordRPCManager:
    """
    Manages Discord Rich Presence via IPC connection.
    Connects gracefully in a background thread and avoids blocking UI if Discord is closed.
    """
    _instance = None

    def __init__(self):
        self.rpc = None
        self.is_connected = False
        self._start_time = int(time.time())
        self._enabled = True

    @classmethod
    def get(cls) -> "DiscordRPCManager":
        if cls._instance is None:
            cls._instance = DiscordRPCManager()
        return cls._instance

    def initialize(self):
        """Initializes connection to local Discord desktop client on the current thread."""
        self._connect()

    def _connect(self):
        try:
            from pypresence import Presence
            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()
            self.is_connected = True
            logger.info("Discord Rich Presence connected successfully.")
            self.update_activity("Idling in Studio", "0 Emulators Running")
        except Exception as e:
            self.is_connected = False
            logger.debug(f"Discord RPC not available: {e}")

    def update_activity(self, state: str = "Active", details: str = "Managing Scrims"):
        if not self.is_connected or not self.rpc or not self._enabled:
            return
        try:
            self.rpc.update(
                state=state,
                details=details,
                start=self._start_time,
                large_image="https://raw.githubusercontent.com/Mahee000/Booyah-SS/main/src/renderer/logo.png",
                large_text="Booyah Esports Automation",
                small_image="https://raw.githubusercontent.com/Mahee000/Booyah-SS/main/src/renderer/logo.png",
                small_text="Booyah Studio"
            )
        except Exception as e:
            logger.debug(f"Failed to update Discord RPC: {e}")

    def close(self):
        if self.rpc and self.is_connected:
            try:
                self.rpc.close()
            except Exception:
                pass
            self.is_connected = False
