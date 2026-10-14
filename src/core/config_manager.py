import json
import os
from typing import Dict, Any

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_FILE = os.path.join(WORKSPACE_DIR, "node_configs.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "customName": "",
    "mode": "BR",
    "preset": "",
    "webhook": "",
    "autoLobbyReturn": False,
    "lobbyReturnDelay": 3.0,
    "lobbyReturnX": None,
    "lobbyReturnY": None,
    "scanSpeed": 1000,
    "scrollCount": 0,
    "cropX": None,
    "cropY": None,
    "cropW": None,
    "cropH": None,
    "crop2X": 0.03,
    "crop2Y": 0.22,
    "crop2W": 0.93,
    "crop2H": 0.66,
    "captureDelay": 1.0,
    "esportsMode": False,
    "esportsKillPoints": 1,
    "esportsPlacementPoints": [12, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0],
    # Auto Room Creation & Match Schedule Settings
    "autoRoomCreation": False,
    "autoHostLeadTime": 5,
    "autoHostActions": [],
    # Auto Close Room Settings
    "autoCloseRoom": False,
    # Auto Rewards & Winner Detection Settings
    "detectWinners": True,
    "autoRewards": False,
    "gameModeType": "Lone Wolf 2V2",
    "autoRewardMaster": "None",
}

SETTINGS_FILE = os.path.join(WORKSPACE_DIR, "app_settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "volume": 0.75,
    "volume_index": 3,
    "audio_enabled": True,
    # Global Auto Close Room Button Calibrations (percentage 0.0 - 1.0)
    "closeRoomX": 0.982,
    "closeRoomY": 0.046,
    "closeRoomDelay": 8.0,
    "confirmCloseX": 0.873,
    "confirmCloseY": 0.621,
    "confirmCloseDelay": 4.0,
    "extraCloseX": 0.975,
    "extraCloseY": 0.033,
    "extraCloseDelay": 2.0,
    # Resource Governor hardware ceilings
    "max_ram_mb": 800,
    "max_cpu_pct": 75.0,
}

def load_app_settings() -> Dict[str, Any]:
    """Loads global application settings (volume, audio state, etc.)."""
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_app_setting(key: str, value: Any):
    """Auto-saves a single global setting immediately upon change."""
    settings = load_app_settings()
    settings[key] = value
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Error saving global app setting {key}: {e}")

def load_all_configs() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def get_node_config(serial: str) -> Dict[str, Any]:
    all_cfg = load_all_configs()
    cfg = all_cfg.get(serial, {})
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    return merged

def save_node_config(serial: str, config_data: Dict[str, Any]):
    all_cfg = load_all_configs()
    all_cfg[serial] = config_data
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(all_cfg, f, indent=2)
    except Exception as e:
        print(f"Error saving config for {serial}: {e}")
