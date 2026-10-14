# Booyah (v2)

Modern, high-performance Android Emulator Automation & Match Management Studio built specifically for Free Fire tournament scrims and esports operations.

Developed with **PyQt6**, **PaddleOCR**, **ADB**, and an **Obsidian Studio** dark aesthetic.

---

## 📁 Project Architecture

```text
Booyah v2/
├── assets/
│   ├── favicon.ico                 # Multi-resolution Windows app & taskbar icon
│   └── logo.png                    # Brand header logo
├── data/
│   ├── captures/                   # Locally stored match end screenshot captures
│   └── match_history.db            # SQLite persistence for match logs & metadata
├── src/
│   ├── core/                       # Core engine services
│   │   ├── __init__.py
│   │   ├── audio_service.py        # Synthesized acoustic notification engine (44.1kHz PCM)
│   │   ├── automation_worker.py    # Per-emulator QThread state & scanning worker
│   │   ├── config_manager.py       # Node configuration loader & persistence
│   │   ├── discord_notifier.py     # Discord Webhook multi-attachment dispatcher
│   │   ├── emulator_service.py     # High-speed ADB subprocess & frame streaming
│   │   ├── match_database.py       # SQLite database queries & capture retrieval
│   │   ├── match_detector.py       # AI OCR detection matrix (BR, CS, LW)
│   │   └── preset_service.py       # Cloud & local tournament preset loader
│   └── ui/                         # Obsidian Studio user interface
│       ├── __init__.py
│       ├── emulator_tile.py        # Live 16:9 preview tile with dynamic ambient glow
│       ├── main_window.py          # Native 720p Studio dashboard & header
│       ├── match_history_dialog.py # Match results browser & screenshot inspector
│       ├── sidebar_inspector.py    # Node inspector & automation controller
│       └── theme.py                # Obsidian Design System QSS stylesheet
├── tests/
│   └── test_audit.py               # Complete test suite (ADB, OCR, UI, Audio)
├── main.py                         # Application entrypoint & Windows AppUserModelID
├── node_configs.json               # Local emulator configuration settings
├── presets_cache.json              # Cached game presets & crop definitions
├── requirements.txt                # Python dependencies
└── README.md
```

---

## ⚡ Game Mode Detection & Support

| Mode | Key OCR Signals & Signatures | Features Supported |
| :--- | :--- | :--- |
| **Battle Royale (BR)** | Multi-Eliminations, Summary Header, Scoreboard | Multi-page scroll capture (`scrollCount`, 1.0s settle delay), Multi-image Discord embed |
| **Clash Squad (CS)** | Round wins, Howlers/Warbringers, Scoreboard, KDA/DMG | In-game HUD noise suppression, Instant victory capture |
| **Lone Wolf (LW)** | Round indicator, Lone Wolf Scoreboard, Kills/DMG | In-game radar suppression, Post-match cooldown |

---

## 🛠️ Setup & Running

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Booyah Studio:**
   ```bash
   python main.py
   ```

3. **Run unit tests:**
   ```bash
   python -m unittest tests/test_audit.py
   ```
