# -*- coding: utf-8 -*-
import os
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QCheckBox, QFrame,
    QTextEdit, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QCoreApplication
from src.core.config_manager import get_node_config, save_node_config
from src.ui.theme import VSCODE_THEME


class AutoRewardsDialog(QDialog):
    """
    Dialog for configuring Auto Winner Detection & Auto Rewards:
    - Game Mode Target (Lone Wolf 1V1, Lone Wolf 2V2, Clash Squad 4V4, Lose To Win)
    - Auto-Award Losers switch for Lose To Win (LTW) tournaments
    - Live Test OCR tool on Lone Wolf/CS scoreboard screenshots
    """
    def __init__(self, serial: str, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.setWindowTitle(f"Winner Detection & Auto Rewards - {serial}")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(480, 520)
        self.resize(500, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.cfg = get_node_config(self.serial)
        self.setStyleSheet(VSCODE_THEME)
        self._init_ui()

    def _init_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(20, 20, 20, 20)
        vbox.setSpacing(14)

        # Header Title
        title_lbl = QLabel("Auto Winner Detection & Rewards")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f0f6fc;")
        vbox.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Detects match winners directly from the Lone Wolf / Clash Squad scoreboard.\n"
            "Automatically inverts results if 'Lose To Win' tournament rules are selected."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.4;")
        vbox.addWidget(desc_lbl)

        # Enable Toggle Rows Card
        toggle_frame = QFrame()
        toggle_frame.setStyleSheet("QFrame { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        t_layout = QVBoxLayout(toggle_frame)
        t_layout.setContentsMargins(14, 12, 14, 12)
        t_layout.setSpacing(10)

        self.enable_chk = QCheckBox("Enable Winner Detection upon Match Conclusion")
        self.enable_chk.setChecked(bool(self.cfg.get("detectWinners", True)))
        self.enable_chk.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 12px;")
        t_layout.addWidget(self.enable_chk)

        self.auto_reward_chk = QCheckBox("Enable Auto Rewards on Master Emulator (Verify & Payout)")
        self.auto_reward_chk.setChecked(bool(self.cfg.get("autoRewards", False)))
        self.auto_reward_chk.setStyleSheet("font-weight: 600; color: #4ade80; font-size: 12px;")
        t_layout.addWidget(self.auto_reward_chk)

        # Master Emulator Selection Row
        master_row = QHBoxLayout()
        master_row.setSpacing(8)
        master_lbl = QLabel("Master Emulator:")
        master_lbl.setStyleSheet("color: #c9d1d9; font-size: 12px; font-weight: 600;")
        master_row.addWidget(master_lbl)

        self.master_combo = QComboBox()
        self.master_combo.addItem("None (Disabled)", "None")
        try:
            from src.core.emulator_service import EmulatorService
            svc = EmulatorService()
            connected = svc.get_connected_devices(auto_scan=False)
            for dev in connected:
                d_serial = dev["serial"]
                if d_serial != self.serial:
                    self.master_combo.addItem(f"{dev.get('alias', d_serial)} ({d_serial})", d_serial)
        except Exception:
            pass

        saved_master = self.cfg.get("autoRewardMaster") or self.cfg.get("autoHostMaster") or "None"
        idx = self.master_combo.findData(saved_master)
        if idx >= 0:
            self.master_combo.setCurrentIndex(idx)
        self.master_combo.setFixedHeight(28)
        master_row.addWidget(self.master_combo, 1)
        t_layout.addLayout(master_row)

        vbox.addWidget(toggle_frame)

        # Mode Selection Card
        mode_card = QFrame()
        mode_card.setStyleSheet("QFrame { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        mc_layout = QVBoxLayout(mode_card)
        mc_layout.setContentsMargins(14, 12, 14, 12)
        mc_layout.setSpacing(8)

        lbl_mode = QLabel("Target Tournament Game Mode:")
        lbl_mode.setStyleSheet("color: #c9d1d9; font-size: 12px; font-weight: 600;")
        mc_layout.addWidget(lbl_mode)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Lone Wolf 2V2",
            "Lone Wolf 1V1",
            "Clash Squad 4V4",
            "Lose To Win (LTW - Reward Losers)"
        ])
        saved_mode = self.cfg.get("gameModeType", "Lone Wolf 2V2")
        idx = self.mode_combo.findText(saved_mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        elif "lose" in saved_mode.lower() or "ltw" in saved_mode.lower():
            self.mode_combo.setCurrentIndex(3)
        self.mode_combo.setFixedHeight(32)
        mc_layout.addWidget(self.mode_combo)
        vbox.addWidget(mode_card)

        # Live Test OCR Section
        test_frame = QFrame()
        test_frame.setStyleSheet("QFrame { background-color: #0b0e14; border: 1px solid #262c36; border-radius: 6px; }")
        tf_layout = QVBoxLayout(test_frame)
        tf_layout.setContentsMargins(12, 10, 12, 10)
        tf_layout.setSpacing(8)

        tf_header = QHBoxLayout()
        tf_title = QLabel("LIVE SCOREBOARD OCR TESTER")
        tf_title.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        tf_header.addWidget(tf_title)
        tf_header.addStretch()

        self.test_btn = QPushButton("Upload & Test Screenshot")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b1d0c;
                color: #fbbf24;
                border: 1px solid #854d0e;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #45290a;
                color: #ffffff;
            }
        """)
        self.test_btn.clicked.connect(self._test_screenshot)
        tf_header.addWidget(self.test_btn)
        tf_layout.addLayout(tf_header)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Upload a Lone Wolf or Clash Squad scoreboard screenshot to test winner detection...")
        self.preview_text.setFixedHeight(140)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #07090d;
                color: #38bdf8;
                border: 1px solid #1f2937;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.3;
                padding: 6px;
            }
        """)
        tf_layout.addWidget(self.preview_text)
        vbox.addWidget(test_frame)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 5px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        vbox.addLayout(btn_row)

    def _test_screenshot(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Scoreboard Screenshot to Test",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path or not os.path.exists(file_path):
            return

        self.preview_text.setPlainText("Processing scoreboard with Winner Detection engine in background... Please wait...")
        self.test_btn.setEnabled(False)

        from PyQt6.QtCore import QThread, pyqtSignal
        from PIL import Image

        mode_text = self.mode_combo.currentText()

        class OcrWorker(QThread):
            finished = pyqtSignal(str)
            error = pyqtSignal(str)

            def run(self):
                try:
                    from src.core.winner_detector import LoneWolfWinnerDetector
                    img = Image.open(file_path)
                    detector = LoneWolfWinnerDetector()
                    res = detector.determine_match_winners(img, game_mode=mode_text)

                    output = "# **WINNER DETECTION RESULTS**\n```\n"
                    output += f"Game Mode: {mode_text}\n"
                    output += f"Total Active Slots: {res.get('active_slots')}\n\n"
                    output += f"WINNERS: {', '.join(res.get('winners', [])) or 'None'}\n"
                    output += "```"
                    self.finished.emit(output)
                except Exception as e:
                    self.error.emit(str(e))

        self._worker = OcrWorker(self)
        self._worker.finished.connect(lambda out: self._on_test_finished(out))
        self._worker.error.connect(lambda err: self._on_test_error(err))
        self._worker.start()

    def _on_test_finished(self, text: str):
        self.preview_text.setPlainText(text)
        self.test_btn.setEnabled(True)

    def _on_test_error(self, err: str):
        self.preview_text.setPlainText(f"Error parsing scoreboard:\n{err}")
        self.test_btn.setEnabled(True)

    def _save(self):
        self.cfg["detectWinners"] = self.enable_chk.isChecked()
        self.cfg["autoRewards"] = self.auto_reward_chk.isChecked()
        self.cfg["gameModeType"] = self.mode_combo.currentText()
        master_val = self.master_combo.currentData()
        if master_val:
            self.cfg["autoRewardMaster"] = master_val
        save_node_config(self.serial, self.cfg)
        self.accept()
