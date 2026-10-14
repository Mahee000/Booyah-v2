# -*- coding: utf-8 -*-
import os
import time
from typing import Dict, Optional
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QScrollArea, QSplitter, QStatusBar,
    QFrame, QLineEdit, QPlainTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QIcon, QPixmap

from src.core.emulator_service import EmulatorService
from src.core.config_manager import get_node_config, load_app_settings, save_app_setting
from src.core.automation_worker import EmulatorAutomationWorker
from src.core.audio_service import AudioEngine, play_sound
from src.core.discord_rpc import DiscordRPCManager
from src.ui.theme import VSCODE_THEME
from src.ui.emulator_tile import EmulatorTile
from src.ui.sidebar_inspector import SidebarInspector


class VolumeButton(QPushButton):
    """
    Volume control button:
    - Left Click: Increase volume (up to 100%)
    - Right Click: Decrease volume (down to Muted 0%)
    """
    volume_up = pyqtSignal()
    volume_down = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.volume_up.emit()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.volume_down.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


class MainWindow(QMainWindow):
    """
    Main Studio Window:
    - Top Obsidian Header with live device count, Sound toggle, and Refresh button
    - Left Scrollable Dashboard displaying live 16:9 emulator tiles
    - Right Inspector Dock for per-emulator configuration and automation controls
    - Collapsible bottom Console Drawer for live logs
    - Bottom Status Bar
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Booyah")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Native 720p resolution with responsive resizing
        self.setMinimumSize(1000, 600)
        self.resize(1280, 720)

        self.service = EmulatorService()
        self.tiles: Dict[str, EmulatorTile] = {}
        self.workers: Dict[str, EmulatorAutomationWorker] = {}
        self.selected_serial: Optional[str] = None

        self._init_ui()
        self.setStyleSheet(VSCODE_THEME)

        # Initialize Discord Rich Presence
        DiscordRPCManager.get().initialize()

        self.refresh_devices()

    def _init_ui(self):
        root = QWidget()
        root.setObjectName("CentralWidget")
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header (Obsidian Studio Header)
        header = QFrame()
        header.setObjectName("HeaderFrame")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 10, 18, 10)
        h_layout.setSpacing(12)

        # Brand Logo + Title Cluster
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(10)

        logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.png"))
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            logo_lbl.setObjectName("HeaderLogo")
            logo_lbl.setFixedSize(26, 26)
            pix = QPixmap(logo_path).scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            brand_layout.addWidget(logo_lbl)

        title = QLabel("BOOYAH")
        title.setObjectName("HeaderTitle")
        brand_layout.addWidget(title)

        self.status_badge = QLabel("0 EMULATORS")
        self.status_badge.setObjectName("BadgeNeutral")
        brand_layout.addWidget(self.status_badge)

        h_layout.addLayout(brand_layout)
        h_layout.addStretch()

        # Group 1: Connect Box Pill
        connect_pill = QFrame()
        connect_pill.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 2px;")
        cp_layout = QHBoxLayout(connect_pill)
        cp_layout.setContentsMargins(6, 2, 6, 2)
        cp_layout.setSpacing(6)

        self.manual_ip_input = QLineEdit()
        self.manual_ip_input.setPlaceholderText("ADB IP: 127.0.0.1:5555")
        self.manual_ip_input.setFixedWidth(150)
        self.manual_ip_input.setFixedHeight(26)
        self.manual_ip_input.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #f0f6fc; padding-left: 4px;")
        cp_layout.addWidget(self.manual_ip_input)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedHeight(26)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #be123c;
                color: #ffffff;
                border: 1px solid #e11d48;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e11d48;
            }
        """)
        self.connect_btn.setToolTip("Connect emulator manually via ADB IP:Port")
        self.connect_btn.clicked.connect(self._manual_connect)
        cp_layout.addWidget(self.connect_btn)

        h_layout.addWidget(connect_pill)

        # Subtle Vertical Divider
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #21262d; margin: 4px 4px;")
        h_layout.addWidget(sep1)

        # Group 2: Action Tools (Volume, History, Logs, Refresh)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(8)

        # Sound volume levels: 0% -> 25% -> 50% -> 75% -> 100%
        self.volume_levels = [0.0, 0.25, 0.50, 0.75, 1.0]
        settings = load_app_settings()
        self.vol_index = max(0, min(len(self.volume_levels) - 1, int(settings.get("volume_index", 3))))
        init_vol = self.volume_levels[self.vol_index]
        AudioEngine.set_volume(init_vol)
        AudioEngine.set_enabled(init_vol > 0.0)

        initial_btn_text = "[M] Muted" if init_vol == 0.0 else f"Vol: {int(init_vol * 100)}%"
        self.audio_btn = VolumeButton(initial_btn_text)
        self.audio_btn.setObjectName("HeaderRefreshBtn")
        self.audio_btn.setFixedHeight(30)
        self.audio_btn.setToolTip("Volume Control:\n  Left-Click: Volume Up\n  Right-Click: Volume Down")
        self.audio_btn.volume_up.connect(self._volume_up)
        self.audio_btn.volume_down.connect(self._volume_down)
        tools_layout.addWidget(self.audio_btn)

        self.history_btn = QPushButton("History")
        self.history_btn.setObjectName("HeaderRefreshBtn")
        self.history_btn.setFixedHeight(30)
        self.history_btn.setToolTip("Browse Match Result History & Captures")
        self.history_btn.clicked.connect(self._open_match_history)
        tools_layout.addWidget(self.history_btn)

        self.console_toggle_btn = QPushButton("Logs [^]")
        self.console_toggle_btn.setObjectName("HeaderRefreshBtn")
        self.console_toggle_btn.setFixedHeight(30)
        self.console_toggle_btn.setToolTip("Toggle Bottom Live Console Logs")
        self.console_toggle_btn.clicked.connect(self._toggle_console)
        tools_layout.addWidget(self.console_toggle_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("HeaderRefreshBtn")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self.refresh_devices)
        tools_layout.addWidget(self.refresh_btn)

        h_layout.addLayout(tools_layout)
        main_layout.addWidget(header)

        # 2. Main Horizontal Splitter: Left (Grid + Console Drawer) + Right Sidebar
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # Left Vertical Splitter: Preview Grid on top, Console drawer on bottom
        self.left_vsplitter = QSplitter(Qt.Orientation.Vertical)
        self.left_vsplitter.setHandleWidth(2)

        # Dashboard Grid Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_widget = QWidget()
        self.cards_layout = QGridLayout(self.grid_widget)
        self.cards_layout.setSpacing(14)
        self.cards_layout.setContentsMargins(16, 16, 16, 16)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_layout.setColumnStretch(0, 1)
        self.cards_layout.setColumnStretch(1, 1)
        scroll.setWidget(self.grid_widget)
        self.left_vsplitter.addWidget(scroll)

        # Collapsible Bottom Console Drawer
        self.console_frame = QFrame()
        self.console_frame.setObjectName("ConsoleFrame")
        self.console_frame.setStyleSheet("background-color: #0b0e14; border-top: 1px solid #21262d;")
        c_layout = QVBoxLayout(self.console_frame)
        c_layout.setContentsMargins(12, 8, 12, 8)
        c_layout.setSpacing(6)

        c_header = QHBoxLayout()
        c_title = QLabel("LIVE CONSOLE & AUTOMATION LOGS")
        c_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #f43f5e; letter-spacing: 0.8px;")
        c_header.addWidget(c_title)
        c_header.addStretch()

        clear_log_btn = QPushButton("Clear")
        clear_log_btn.setFixedHeight(24)
        clear_log_btn.setMinimumWidth(56)
        clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #161b22;
                color: #8b949e;
                border: 1px solid #30363d;
                font-size: 11px;
                font-weight: 500;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #21262d;
                color: #f0f6fc;
                border-color: #58a6ff;
            }
        """)
        clear_log_btn.clicked.connect(self._clear_console)
        c_header.addWidget(clear_log_btn)

        hide_log_btn = QPushButton("X")
        hide_log_btn.setFixedSize(24, 24)
        hide_log_btn.setToolTip("Hide Console Drawer")
        hide_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #161b22;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #26161a;
                color: #f87171;
                border-color: #ef4444;
            }
        """)
        hide_log_btn.clicked.connect(self._toggle_console)
        c_header.addWidget(hide_log_btn)
        c_layout.addLayout(c_header)

        self.console_log_view = QPlainTextEdit()
        self.console_log_view.setReadOnly(True)
        self.console_log_view.setMaximumBlockCount(500)
        self.console_log_view.setStyleSheet(
            "QPlainTextEdit { background-color: #07090d; color: #c9d1d9; font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 12px; border: 1px solid #21262d; border-radius: 4px; padding: 6px; }"
        )
        c_layout.addWidget(self.console_log_view, 1)

        self.left_vsplitter.addWidget(self.console_frame)
        self.console_frame.hide()
        self.left_vsplitter.setSizes([720, 0])

        splitter.addWidget(self.left_vsplitter)

        # Sidebar Inspector
        self.sidebar = SidebarInspector()
        self.sidebar.config_saved.connect(self._on_config_saved)
        self.sidebar.start_toggled.connect(self._on_start_toggled)
        splitter.addWidget(self.sidebar)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([940, 400])
        main_layout.addWidget(splitter, 1)

        # 3. Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setFixedHeight(26)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _volume_up(self):
        if self.vol_index < len(self.volume_levels) - 1:
            self.vol_index += 1
        self._apply_volume()

    def _volume_down(self):
        if self.vol_index > 0:
            self.vol_index -= 1
        self._apply_volume()

    def _apply_volume(self):
        vol = self.volume_levels[self.vol_index]
        save_app_setting("volume_index", self.vol_index)
        save_app_setting("volume", vol)

        if vol == 0.0:
            AudioEngine.set_enabled(False)
            AudioEngine.set_volume(0.0)
            save_app_setting("audio_enabled", False)
            self.audio_btn.setText("[M] Muted")
        else:
            AudioEngine.set_enabled(True)
            AudioEngine.set_volume(vol)
            save_app_setting("audio_enabled", True)
            pct = int(vol * 100)
            self.audio_btn.setText(f"Vol: {pct}%")

    def _open_match_history(self):
        from src.ui.match_history_dialog import MatchHistoryDialog
        dialog = MatchHistoryDialog(self)
        dialog.exec()

    def refresh_devices(self):
        devices = self.service.get_connected_devices()

        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        self.tiles.clear()

        if not devices:
            self.status_badge.setText("0 EMULATORS")
            self.status_badge.setObjectName("BadgeNeutral")
            lbl_empty = QLabel("No active emulators detected.\nStart BlueStacks or LDPlayer and click 'Refresh'.")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setStyleSheet("color: #6e7681; font-size: 13px; padding: 60px; line-height: 1.6;")
            self.cards_layout.addWidget(lbl_empty, 0, 0)
            self.status_bar.showMessage("No devices connected")
            return

        self.status_badge.setText(f"{len(devices)} EMULATORS")
        self.status_badge.setObjectName("BadgeSuccess")

        cols = 2
        for idx, dev in enumerate(devices):
            serial = dev["serial"]
            tile = EmulatorTile(serial)
            tile.tile_clicked.connect(self.select_emulator)
            self.tiles[serial] = tile

            row = idx // cols
            col = idx % cols
            self.cards_layout.addWidget(tile, row, col)

        self.status_bar.showMessage(f"Loaded {len(devices)} emulators")
        self._refresh_previews()

        if devices:
            target = self.selected_serial if (self.selected_serial and self.selected_serial in self.tiles) else devices[0]["serial"]
            self.select_emulator(target)

    def select_emulator(self, serial: str):
        self.selected_serial = serial
        for s, tile in self.tiles.items():
            tile.set_selected(s == serial)

        is_running = (serial in self.workers)
        self.sidebar.load_emulator(serial, is_running)
        self.status_bar.showMessage(f"Selected: {serial}")

    def _on_config_saved(self, serial: str, new_config: dict):
        if serial in self.tiles:
            self.tiles[serial].update_name(new_config.get("customName", ""))

        if serial in self.workers:
            self.workers[serial].update_config(new_config)

        self.status_bar.showMessage(f"Saved: {serial}")

    def _refresh_previews(self):
        for serial, tile in self.tiles.items():
            if serial not in self.workers:
                img = self.service.capture_screenshot(serial)
                if img:
                    tile.update_preview(img)

    def _on_start_toggled(self, serial: str, is_running: bool):
        cfg = get_node_config(serial)
        name = cfg.get("customName") or serial

        if is_running:
            worker = EmulatorAutomationWorker(serial, self.service, cfg)
            worker.frame_ready.connect(self._on_worker_frame)
            worker.state_changed.connect(self._on_worker_state)
            worker.log_message.connect(self._on_worker_log)
            self.workers[serial] = worker
            worker.start()
            if serial in self.tiles:
                self.tiles[serial].set_phase("IN_GAME", "RUNNING")
            self.status_bar.showMessage(f"{name}: STARTED")
            DiscordRPCManager.get().update_activity(
                state=f"Scanning {len(self.workers)} Instance(s)",
                details=f"Active on {name}"
            )
        else:
            if serial in self.workers:
                worker = self.workers.pop(serial)
                worker.stop()
                worker.wait(2000)
            if serial in self.tiles:
                self.tiles[serial].set_phase("IDLE", "STOPPED")
            self.status_bar.showMessage(f"{name}: STOPPED")
            count = len(self.workers)
            if count > 0:
                DiscordRPCManager.get().update_activity(
                    state=f"Scanning {count} Instance(s)",
                    details="Monitoring Scrims"
                )
            else:
                DiscordRPCManager.get().update_activity(
                    state="Idling in Studio",
                    details="0 Emulators Running"
                )

    def _on_worker_frame(self, serial: str, frame: Image.Image):
        if serial in self.tiles:
            self.tiles[serial].update_preview(frame)

    def _on_worker_state(self, serial: str, state: str):
        if serial in self.tiles:
            labels = {
                "IDLE": "IDLE",
                "IN_GAME": "IN-GAME",
                "RESULT_SCREEN": "MATCH WON",
                "MATCH": "MATCH WON",
                "WAIT": "SETTLING 3S",
                "SLEEP": "COOLDOWN"
            }
            lbl = labels.get(state, state)
            self.tiles[serial].set_phase(state, lbl)

    def _manual_connect(self):
        addr = self.manual_ip_input.text().strip()
        if not addr:
            self.status_bar.showMessage("Please enter IP:Port (e.g. 127.0.0.1:5555)")
            return
        self.status_bar.showMessage(f"Connecting to {addr}...")
        ok, msg = self.service.connect_device(addr)
        if ok:
            self.status_bar.showMessage(f"Connected: {msg}")
            self._append_console_log("SYSTEM", f"Successfully connected to {addr}: {msg}", "SUCCESS")
            self.manual_ip_input.clear()
            self.refresh_devices()
        else:
            self.status_bar.showMessage(f"Connect failed: {msg}")
            self._append_console_log("SYSTEM", f"Connect to {addr} failed: {msg}", "ERROR")
            QMessageBox.warning(self, "Connection Failed", f"Could not connect to {addr}:\n\n{msg}")

    def _toggle_console(self):
        visible = not self.console_frame.isVisible()
        self.console_frame.setVisible(visible)
        if visible:
            self.console_toggle_btn.setText("Logs [v]")
            self.left_vsplitter.setSizes([520, 180])
        else:
            self.console_toggle_btn.setText("Logs [^]")
            self.left_vsplitter.setSizes([720, 0])

    def _clear_console(self):
        self.console_log_view.clear()

    def _append_console_log(self, serial: str, msg: str, level: str):
        color_map = {
            "MATCH": "#3fb950",
            "SUCCESS": "#3fb950",
            "ERROR": "#f85149",
            "WAIT": "#d29922",
            "SCROLL": "#bc8cff",
            "LOBBY": "#58a6ff",
            "INFO": "#8b949e"
        }
        col = color_map.get(level.upper(), "#c9d1d9")
        ts = time.strftime("%H:%M:%S")
        html_msg = (
            f"<span style='color: #6e7681;'>[{ts}]</span> "
            f"<span style='color: #58a6ff;'>[{serial}]</span> "
            f"<b style='color: {col};'>[{level}]</b> "
            f"<span style='color: {col};'>{msg}</span>"
        )
        self.console_log_view.appendHtml(html_msg)

    def _on_worker_log(self, serial: str, msg: str, level: str):
        print(f"[{level}] [{serial}] {msg}")
        self.status_bar.showMessage(f"{serial}: {msg}")
        self._append_console_log(serial, msg, level)

    def closeEvent(self, event):
        for worker in self.workers.values():
            worker.stop()
            worker.wait(1000)
        super().closeEvent(event)
