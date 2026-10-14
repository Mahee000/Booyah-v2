# -*- coding: utf-8 -*-
from typing import Optional
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QDoubleSpinBox, QPushButton, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from src.core.preset_service import PresetService, MODES
from src.core.config_manager import get_node_config, save_node_config
from src.core.audio_service import play_sound


class SidebarInspector(QFrame):
    """
    Modular Sidebar Inspector:
    - Emulator Identity Header (Name, Serial, IDLE/RUNNING badge)
    - Scrollable Form: Configuration, Automation, Studio Tools
    - Pinned Action Buttons: Save Settings + Start/Stop Scanning
    """
    config_saved = pyqtSignal(str, dict)
    start_toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_serial: Optional[str] = None
        self.is_running = False
        self._is_loading = False

        self.setObjectName("SidebarFrame")
        self.setMinimumWidth(350)
        self.setMaximumWidth(450)

        main_vbox = QVBoxLayout(self)
        main_vbox.setContentsMargins(14, 14, 14, 14)
        main_vbox.setSpacing(10)

        # 1. Empty State (When no emulator is selected)
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_no_sel = QLabel("Select an emulator preview\nto inspect and configure properties")
        lbl_no_sel.setStyleSheet("color: #6e7681; font-size: 13px; line-height: 1.6; text-align: center;")
        lbl_no_sel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(lbl_no_sel)
        main_vbox.addWidget(self.empty_widget, 1)

        # 2. Form Container Widget
        self.form_widget = QWidget()
        form_outer_vbox = QVBoxLayout(self.form_widget)
        form_outer_vbox.setContentsMargins(0, 0, 0, 0)
        form_outer_vbox.setSpacing(10)

        # Header: Name, Serial, Status Badge
        header_row = QHBoxLayout()
        v_titles = QVBoxLayout()
        v_titles.setSpacing(2)
        self.header_title = QLabel("Emulator")
        self.header_title.setStyleSheet("color: #f0f6fc; font-size: 16px; font-weight: 700;")
        self.header_serial = QLabel("serial")
        self.header_serial.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 500;")
        v_titles.addWidget(self.header_title)
        v_titles.addWidget(self.header_serial)
        header_row.addLayout(v_titles)

        header_row.addStretch()

        self.status_badge = QLabel("IDLE")
        self.status_badge.setStyleSheet(
            "background-color: #21262d; color: #8b949e; border: 1px solid #30363d; "
            "border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 10px;"
        )
        header_row.addWidget(self.status_badge)
        form_outer_vbox.addLayout(header_row)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("color: #21262d; margin: 2px 0;")
        form_outer_vbox.addWidget(div1)

        # Scrollable area for the form fields so nothing clips on any display resolution
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        form_vbox = QVBoxLayout(scroll_content)
        form_vbox.setContentsMargins(0, 0, 4, 0)
        form_vbox.setSpacing(8)

        # Label styling helper
        _lbl_css = "color: #8b949e; font-size: 12px; font-weight: 500; min-width: 65px;"

        # Category 1: CONFIGURATION CARD
        card_config = QFrame()
        card_config.setObjectName("CardConfig")
        card_config.setStyleSheet("QFrame#CardConfig { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        cc_layout = QVBoxLayout(card_config)
        cc_layout.setContentsMargins(12, 10, 12, 10)
        cc_layout.setSpacing(8)

        lbl_cat_config = QLabel("CONFIGURATION")
        lbl_cat_config.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        cc_layout.addWidget(lbl_cat_config)

        cfg_form = QFormLayout()
        cfg_form.setContentsMargins(0, 0, 0, 0)
        cfg_form.setHorizontalSpacing(10)
        cfg_form.setVerticalSpacing(8)
        cfg_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        cfg_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        lbl_name = QLabel("Alias:")
        lbl_name.setStyleSheet(_lbl_css)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Scrim Host 1")
        self.name_input.setFixedHeight(30)
        cfg_form.addRow(lbl_name, self.name_input)

        lbl_mode = QLabel("Mode:")
        lbl_mode.setStyleSheet(_lbl_css)
        self.mode_combo = QComboBox()
        self.mode_combo.setFixedHeight(30)
        for m in MODES:
            self.mode_combo.addItem(m["name"], m["id"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        cfg_form.addRow(lbl_mode, self.mode_combo)

        lbl_preset = QLabel("Preset:")
        lbl_preset.setStyleSheet(_lbl_css)
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedHeight(30)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        cfg_form.addRow(lbl_preset, self.preset_combo)

        lbl_wh = QLabel("Webhook:")
        lbl_wh.setStyleSheet(_lbl_css)
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("Discord Webhook URL...")
        self.webhook_input.setFixedHeight(30)
        cfg_form.addRow(lbl_wh, self.webhook_input)

        cc_layout.addLayout(cfg_form)
        form_vbox.addWidget(card_config)

        # Category 2: AUTOMATION CARD
        card_auto = QFrame()
        card_auto.setObjectName("CardAuto")
        card_auto.setStyleSheet("QFrame#CardAuto { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        ca_layout = QVBoxLayout(card_auto)
        ca_layout.setContentsMargins(12, 10, 12, 10)
        ca_layout.setSpacing(8)

        lbl_cat_auto = QLabel("AUTOMATION")
        lbl_cat_auto.setStyleSheet("color: #3fb950; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        ca_layout.addWidget(lbl_cat_auto)

        auto_form = QFormLayout()
        auto_form.setContentsMargins(0, 0, 0, 0)
        auto_form.setHorizontalSpacing(10)
        auto_form.setVerticalSpacing(8)
        auto_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        auto_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Auto Return Toggle
        self.auto_return_chk = QCheckBox("Auto Lobby Return")
        self.auto_return_chk.toggled.connect(self._auto_save_if_loaded)
        auto_form.addRow("", self.auto_return_chk)

        lbl_delay = QLabel("Delay:")
        lbl_delay.setStyleSheet(_lbl_css)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.5, 30.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setSuffix(" s")
        self.delay_spin.setFixedHeight(30)
        self.delay_spin.valueChanged.connect(self._auto_save_if_loaded)
        auto_form.addRow(lbl_delay, self.delay_spin)

        # Dynamic Coordinates Row
        lbl_coords = QLabel("Tap Pos:")
        lbl_coords.setStyleSheet(_lbl_css)
        coords_row = QHBoxLayout()
        coords_row.setContentsMargins(0, 0, 0, 0)
        coords_row.setSpacing(6)

        self.lobby_x_spin = QDoubleSpinBox()
        self.lobby_x_spin.setRange(0.0, 1.0)
        self.lobby_x_spin.setSingleStep(0.01)
        self.lobby_x_spin.setDecimals(2)
        self.lobby_x_spin.setPrefix("X: ")
        self.lobby_x_spin.setFixedHeight(30)
        self.lobby_x_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.lobby_x_spin.valueChanged.connect(self._auto_save_if_loaded)
        coords_row.addWidget(self.lobby_x_spin, 1)

        self.lobby_y_spin = QDoubleSpinBox()
        self.lobby_y_spin.setRange(0.0, 1.0)
        self.lobby_y_spin.setSingleStep(0.01)
        self.lobby_y_spin.setDecimals(2)
        self.lobby_y_spin.setPrefix("Y: ")
        self.lobby_y_spin.setFixedHeight(30)
        self.lobby_y_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.lobby_y_spin.valueChanged.connect(self._auto_save_if_loaded)
        coords_row.addWidget(self.lobby_y_spin, 1)

        self.lobby_reset_btn = QPushButton("Auto")
        self.lobby_reset_btn.setToolTip("Reset to game mode's automatic dynamic coordinates")
        self.lobby_reset_btn.setFixedHeight(30)
        self.lobby_reset_btn.setMinimumWidth(58)
        self.lobby_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)
        self.lobby_reset_btn.clicked.connect(self._reset_lobby_coords_to_auto)
        coords_row.addWidget(self.lobby_reset_btn)

        auto_form.addRow(lbl_coords, coords_row)

        _action_btn_css = """
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
                border-color: #f43f5e;
            }
        """

        # Auto Create Room Row (formerly Auto Host)
        auto_host_row = QHBoxLayout()
        auto_host_row.setContentsMargins(0, 0, 0, 0)
        auto_host_row.setSpacing(6)
        self.auto_host_chk = QCheckBox("Auto Create Room")
        self.auto_host_chk.toggled.connect(self._auto_save_if_loaded)
        auto_host_row.addWidget(self.auto_host_chk, 1)

        self.auto_host_btn = QPushButton("Sequence")
        self.auto_host_btn.setFixedHeight(28)
        self.auto_host_btn.setToolTip("Configure Room Creation sequence steps & Lead Time")
        self.auto_host_btn.setStyleSheet(_action_btn_css)
        self.auto_host_btn.clicked.connect(self._open_auto_host_dialog)
        auto_host_row.addWidget(self.auto_host_btn)
        auto_form.addRow("", auto_host_row)

        # Auto Close Room Row
        auto_close_row = QHBoxLayout()
        auto_close_row.setContentsMargins(0, 0, 0, 0)
        auto_close_row.setSpacing(6)
        self.auto_close_chk = QCheckBox("Auto Close Room")
        self.auto_close_chk.toggled.connect(self._auto_save_if_loaded)
        auto_close_row.addWidget(self.auto_close_chk, 1)

        self.auto_close_btn = QPushButton("Calibrate")
        self.auto_close_btn.setFixedHeight(28)
        self.auto_close_btn.setToolTip("Configure Room Close sequence coordinates and delays")
        self.auto_close_btn.setStyleSheet(_action_btn_css)
        self.auto_close_btn.clicked.connect(self._open_auto_close_dialog)
        auto_close_row.addWidget(self.auto_close_btn)
        auto_form.addRow("", auto_close_row)

        # Auto Winner Detection Row
        auto_winner_row = QHBoxLayout()
        auto_winner_row.setContentsMargins(0, 0, 0, 0)
        auto_winner_row.setSpacing(6)
        self.auto_winner_chk = QCheckBox("Auto Winner Detection")
        self.auto_winner_chk.toggled.connect(self._auto_save_if_loaded)
        auto_winner_row.addWidget(self.auto_winner_chk, 1)

        self.auto_reward_btn = QPushButton("Settings")
        self.auto_reward_btn.setFixedHeight(28)
        self.auto_reward_btn.setToolTip("Configure Lone Wolf / Clash Squad / Lose To Win (LTW) Winner Detection & Auto Rewards")
        self.auto_reward_btn.setStyleSheet(_action_btn_css)
        self.auto_reward_btn.clicked.connect(self._open_auto_rewards_dialog)
        auto_winner_row.addWidget(self.auto_reward_btn)
        auto_form.addRow("", auto_winner_row)

        # Auto Rewards (Payout) Row
        auto_payout_row = QHBoxLayout()
        auto_payout_row.setContentsMargins(0, 0, 0, 0)
        auto_payout_row.setSpacing(6)
        self.auto_reward_chk = QCheckBox("Auto Rewards (Payout)")
        self.auto_reward_chk.toggled.connect(self._auto_save_if_loaded)
        auto_payout_row.addWidget(self.auto_reward_chk, 1)
        auto_form.addRow("", auto_payout_row)

        ca_layout.addLayout(auto_form)
        form_vbox.addWidget(card_auto)

        # Category 3: TOOLS CARD
        card_tools = QFrame()
        card_tools.setObjectName("CardTools")
        card_tools.setStyleSheet("QFrame#CardTools { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        ct_layout = QVBoxLayout(card_tools)
        ct_layout.setContentsMargins(12, 10, 12, 10)
        ct_layout.setSpacing(8)

        lbl_cat_tools = QLabel("STUDIO TOOLS")
        lbl_cat_tools.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        ct_layout.addWidget(lbl_cat_tools)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)

        self.crop_btn = QPushButton("Crop Editor")
        self.crop_btn.setFixedHeight(32)
        self.crop_btn.setStyleSheet("""
            QPushButton {
                background-color: #10233d;
                color: #38bdf8;
                border: 1px solid #1e40af;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #1e3a8a;
                border-color: #60a5fa;
                color: #ffffff;
            }
        """)
        self.crop_btn.setToolTip("Visually select and calibrate the preset crop area on live screen")
        self.crop_btn.clicked.connect(self._open_crop_editor)
        tools_row.addWidget(self.crop_btn, 1)

        self.esports_btn = QPushButton("Points Table")
        self.esports_btn.setFixedHeight(32)
        self.esports_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b1d0c;
                color: #fbbf24;
                border: 1px solid #854d0e;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #45290a;
                border-color: #facc15;
                color: #ffffff;
            }
        """)
        self.esports_btn.setToolTip("Configure Esports Kill Multipliers and Rank 1-12 Placement Points")
        self.esports_btn.clicked.connect(self._open_esports_points)
        tools_row.addWidget(self.esports_btn, 1)

        ct_layout.addLayout(tools_row)
        form_vbox.addWidget(card_tools)

        form_scroll.setWidget(scroll_content)
        form_outer_vbox.addWidget(form_scroll, 1)

        # Pinned Bottom Buttons Cluster
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.setFixedHeight(34)
        self.save_btn.clicked.connect(self._save_changes)
        btn_row.addWidget(self.save_btn, 1)

        self.run_btn = QPushButton("Start")
        self.run_btn.setObjectName("PrimaryBtn")
        self.run_btn.setFixedHeight(34)
        self.run_btn.clicked.connect(self._toggle_run)
        btn_row.addWidget(self.run_btn, 1)

        form_outer_vbox.addLayout(btn_row)

        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_lbl.setStyleSheet("color: #3fb950; font-size: 12px; font-weight: 600;")
        form_outer_vbox.addWidget(self.feedback_lbl)

        main_vbox.addWidget(self.form_widget, 1)
        self.form_widget.hide()

    def _populate_presets_for_mode(self, mode_id: str):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        presets = PresetService.get_presets_for_mode(mode_id)
        for p in presets:
            self.preset_combo.addItem(p["name"], p["id"])
        self.preset_combo.blockSignals(False)

    def _on_mode_changed(self):
        if self._is_loading:
            return
        mode_id = self.mode_combo.currentData()
        if not mode_id:
            return
        # Automatically update default lobby return coordinates for this mode
        self._update_default_lobby_coords_for_mode(mode_id)
        self._populate_presets_for_mode(mode_id)
        self._on_preset_changed(reset_all=True)

    def _on_preset_changed(self, reset_all: bool = False):
        if self._is_loading:
            return
        preset_id = self.preset_combo.currentData()
        if not preset_id:
            return
        all_presets = PresetService.load_presets()
        p = all_presets.get(preset_id)
        mode = self.mode_combo.currentData() or "BR"
        if p:
            if p.get("webhook"):
                self.webhook_input.setText(p.get("webhook"))

        # When changing preset or mode, reset node-level overrides so the new preset's
        # exact crops, actions, sleep time, log cadence, etc. take effect immediately
        if reset_all or self.current_serial:
            from src.core.preset_service import get_default_room_actions_for_mode, get_default_game_mode_type_for_preset
            cfg = get_node_config(self.current_serial)
            if p:
                cfg["cropX"] = p.get("cropX")
                cfg["cropY"] = p.get("cropY")
                cfg["cropW"] = p.get("cropW")
                cfg["cropH"] = p.get("cropH")
                cfg["scrollCount"] = p.get("scrollCount", 0)
                cfg["crop2X"] = p.get("crop2X", p.get("cropX"))
                cfg["crop2Y"] = p.get("crop2Y", p.get("cropY"))
                cfg["crop2W"] = p.get("crop2W", p.get("cropW"))
                cfg["crop2H"] = p.get("crop2H", p.get("cropH"))
                cfg["sleepTime"] = p.get("sleepTime", 5)
                cfg["logInterval"] = p.get("logInterval", 15)
                cfg["logOffset"] = p.get("logOffset", 0)
                cfg["autoHostActions"] = p.get("autoHostActions") or get_default_room_actions_for_mode(mode)
                # Automatically associate sub-preset with its tournament game mode
                cfg["gameModeType"] = get_default_game_mode_type_for_preset(preset_id, p.get("name", ""), mode)
                save_node_config(self.current_serial, cfg)

        self._auto_save_if_loaded()

    def _auto_save_if_loaded(self):
        if self._is_loading or not self.current_serial:
            return
        self._save_changes(silent=True)

    def load_emulator(self, serial: str, is_running: bool):
        self._is_loading = True
        self.current_serial = serial
        self.is_running = is_running
        self.empty_widget.hide()
        self.form_widget.show()

        self.mode_combo.blockSignals(True)
        self.preset_combo.blockSignals(True)
        self.auto_return_chk.blockSignals(True)
        self.delay_spin.blockSignals(True)
        self.auto_host_chk.blockSignals(True)
        self.auto_close_chk.blockSignals(True)

        try:
            cfg = get_node_config(serial)
            name = cfg.get("customName") or serial
            self.header_title.setText(name)
            self.header_serial.setText(serial)

            self.name_input.setText(cfg.get("customName", ""))

            # 1. Load Mode
            mode = cfg.get("mode", "BR")
            idx = self.mode_combo.findData(mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
            else:
                self.mode_combo.setCurrentIndex(0)
                mode = self.mode_combo.currentData() or "BR"

            # 2. Populate Presets
            self._populate_presets_for_mode(mode)

            # 3. Select Saved Preset
            saved_preset_id = cfg.get("preset")
            if saved_preset_id:
                p_idx = self.preset_combo.findData(saved_preset_id)
                if p_idx >= 0:
                    self.preset_combo.setCurrentIndex(p_idx)
                elif self.preset_combo.count() > 0:
                    self.preset_combo.setCurrentIndex(0)
            elif self.preset_combo.count() > 0:
                self.preset_combo.setCurrentIndex(0)

            # 4. Webhook URL
            saved_webhook = cfg.get("webhook", "")
            if not saved_webhook:
                preset_id = self.preset_combo.currentData()
                if preset_id:
                    all_presets = PresetService.load_presets()
                    p = all_presets.get(preset_id)
                    if p and p.get("webhook"):
                        saved_webhook = p.get("webhook", "")
            self.webhook_input.setText(saved_webhook)

            # 5. Automation settings
            self.auto_return_chk.setChecked(bool(cfg.get("autoLobbyReturn", False)))
            self.delay_spin.setValue(float(cfg.get("lobbyReturnDelay", 3.0)))
            self.auto_host_chk.setChecked(bool(cfg.get("autoRoomCreation", False)))
            self.auto_close_chk.setChecked(bool(cfg.get("autoCloseRoom", False)))
            self.auto_winner_chk.setChecked(bool(cfg.get("detectWinners", True)))
            self.auto_reward_chk.setChecked(bool(cfg.get("autoRewards", False)))

            saved_lx = cfg.get("lobbyReturnX")
            saved_ly = cfg.get("lobbyReturnY")
            if saved_lx is not None and saved_ly is not None:
                self.lobby_x_spin.setValue(float(saved_lx))
                self.lobby_y_spin.setValue(float(saved_ly))
            else:
                self._update_default_lobby_coords_for_mode(mode)

            self._update_run_ui(is_running)
            self.feedback_lbl.setText("")
        finally:
            self.mode_combo.blockSignals(False)
            self.preset_combo.blockSignals(False)
            self.auto_return_chk.blockSignals(False)
            self.delay_spin.blockSignals(False)
            self.lobby_x_spin.blockSignals(False)
            self.lobby_y_spin.blockSignals(False)
            self.auto_host_chk.blockSignals(False)
            self.auto_close_chk.blockSignals(False)
            self.auto_winner_chk.blockSignals(False)
            self.auto_reward_chk.blockSignals(False)
            self._is_loading = False

    def _update_default_lobby_coords_for_mode(self, mode: str):
        if mode == "CS":
            self.lobby_x_spin.setValue(0.88)
            self.lobby_y_spin.setValue(0.92)
        elif mode == "LW":
            self.lobby_x_spin.setValue(0.85)
            self.lobby_y_spin.setValue(0.90)
        else:
            self.lobby_x_spin.setValue(0.86)
            self.lobby_y_spin.setValue(0.91)

    def _reset_lobby_coords_to_auto(self):
        mode = self.mode_combo.currentData() or "BR"
        self._update_default_lobby_coords_for_mode(mode)
        if self.current_serial:
            cfg = get_node_config(self.current_serial)
            cfg["lobbyReturnX"] = None
            cfg["lobbyReturnY"] = None
            save_node_config(self.current_serial, cfg)
            self.feedback_lbl.setText("Set to Auto Mode Preset")
            QTimer.singleShot(2000, lambda: self.feedback_lbl.setText(""))

    def _update_run_ui(self, running: bool):
        self.is_running = running
        if running:
            self.run_btn.setText("Stop")
            self.run_btn.setObjectName("DangerBtn")
            self.status_badge.setText("RUNNING")
            self.status_badge.setStyleSheet(
                "background-color: rgba(46, 160, 67, 0.15); color: #3fb950; border: 1px solid rgba(46, 160, 67, 0.4); "
                "border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 10px;"
            )
        else:
            self.run_btn.setText("Start")
            self.run_btn.setObjectName("PrimaryBtn")
            self.status_badge.setText("IDLE")
            self.status_badge.setStyleSheet(
                "background-color: #21262d; color: #8b949e; border: 1px solid #30363d; "
                "border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 10px;"
            )

        self.style().unpolish(self.run_btn)
        self.style().polish(self.run_btn)

    def _toggle_run(self):
        if not self.current_serial:
            return
        self.is_running = not self.is_running
        self._update_run_ui(self.is_running)
        play_sound("start" if self.is_running else "stop")
        self.start_toggled.emit(self.current_serial, self.is_running)

    def _save_changes(self, silent: bool = False):
        if not self.current_serial:
            return

        preset_id = self.preset_combo.currentData()
        all_presets = PresetService.load_presets()
        p = all_presets.get(preset_id, {})
        cfg = get_node_config(self.current_serial)

        new_config = {
            **cfg,
            "customName": self.name_input.text().strip(),
            "mode": self.mode_combo.currentData(),
            "preset": preset_id,
            "webhook": self.webhook_input.text().strip(),
            "autoLobbyReturn": self.auto_return_chk.isChecked(),
            "lobbyReturnDelay": self.delay_spin.value(),
            "lobbyReturnX": round(self.lobby_x_spin.value(), 2),
            "lobbyReturnY": round(self.lobby_y_spin.value(), 2),
            "autoRoomCreation": self.auto_host_chk.isChecked(),
            "autoCloseRoom": self.auto_close_chk.isChecked(),
            "detectWinners": self.auto_winner_chk.isChecked(),
            "autoRewards": self.auto_reward_chk.isChecked(),
            "autoHostLeadTime": cfg.get("autoHostLeadTime", 5),
            "autoHostActions": cfg.get("autoHostActions") or p.get("autoHostActions", []),
            "cropX": p.get("cropX") if p.get("cropX") is not None else cfg.get("cropX"),
            "cropY": p.get("cropY") if p.get("cropY") is not None else cfg.get("cropY"),
            "cropW": p.get("cropW") if p.get("cropW") is not None else cfg.get("cropW"),
            "cropH": p.get("cropH") if p.get("cropH") is not None else cfg.get("cropH"),
            "scrollCount": p.get("scrollCount", cfg.get("scrollCount", 0)),
            "crop2X": p.get("crop2X") if p.get("crop2X") is not None else cfg.get("crop2X", p.get("cropX")),
            "crop2Y": p.get("crop2Y") if p.get("crop2Y") is not None else cfg.get("crop2Y", p.get("cropY")),
            "crop2W": p.get("crop2W") if p.get("crop2W") is not None else cfg.get("crop2W", p.get("cropW")),
            "crop2H": p.get("crop2H") if p.get("crop2H") is not None else cfg.get("crop2H", p.get("cropH")),
            "sleepTime": p.get("sleepTime", cfg.get("sleepTime", 5)),
            "logInterval": p.get("logInterval", cfg.get("logInterval", 15)),
            "logOffset": p.get("logOffset", cfg.get("logOffset", 0)),
            "esportsMode": cfg.get("esportsMode", False),
            "esportsKillPoints": cfg.get("esportsKillPoints", 1),
            "esportsPlacementPoints": cfg.get("esportsPlacementPoints", [12, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0])
        }

        save_node_config(self.current_serial, new_config)
        self.header_title.setText(new_config["customName"] or self.current_serial)
        if not silent:
            self.feedback_lbl.setText("Saved Settings")
            play_sound("save")
            QTimer.singleShot(2500, lambda: self.feedback_lbl.setText(""))
        self.config_saved.emit(self.current_serial, new_config)

    def _open_auto_host_dialog(self):
        if not self.current_serial:
            return
        self._save_changes(silent=True)
        from src.ui.auto_host_dialog import AutoHostDialog
        from src.core.emulator_service import EmulatorService
        dialog = AutoHostDialog(self.current_serial, EmulatorService(), self)
        if dialog.exec():
            self.load_emulator(self.current_serial, self.is_running)

    def _open_auto_close_dialog(self):
        if not self.current_serial:
            return
        self._save_changes(silent=True)
        from src.ui.auto_close_dialog import AutoCloseDialog
        from src.core.emulator_service import EmulatorService
        dialog = AutoCloseDialog(self.current_serial, EmulatorService(), self)
        if dialog.exec():
            self.load_emulator(self.current_serial, self.is_running)

    def _open_auto_rewards_dialog(self):
        if not self.current_serial:
            return
        self._save_changes(silent=True)
        from src.ui.auto_rewards_dialog import AutoRewardsDialog
        dialog = AutoRewardsDialog(self.current_serial, self)
        if dialog.exec():
            self.load_emulator(self.current_serial, self.is_running)

    def _open_crop_editor(self):
        if not self.current_serial:
            return
        self._save_changes(silent=True)
        from src.ui.crop_editor_dialog import PresetCropVisualEditor
        from src.core.emulator_service import EmulatorService
        dialog = PresetCropVisualEditor(self.current_serial, EmulatorService(), self)
        if dialog.exec():
            self.load_emulator(self.current_serial, self.is_running)

    def _open_esports_points(self):
        if not self.current_serial:
            return
        self._save_changes(silent=True)
        from src.ui.esports_dialog import EsportsPointsDialog
        dialog = EsportsPointsDialog(self.current_serial, self)
        if dialog.exec():
            self.load_emulator(self.current_serial, self.is_running)
