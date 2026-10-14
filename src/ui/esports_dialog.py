# -*- coding: utf-8 -*-
import os
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox, QCheckBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from src.core.config_manager import get_node_config, save_node_config
from src.ui.theme import VSCODE_THEME

DEFAULT_PLACEMENTS = [12, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0]


class EsportsPointsDialog(QDialog):
    """
    Dialog for configuring Esports Kill & Placement points table:
    - Toggle Esports Mode calculation
    - Configurable points per kill (e.g. 1 point)
    - Rank 1 to Rank 12 placement points table
    - Auto-saves to emulator node config
    """
    def __init__(self, serial: str, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.setWindowTitle(f"Esports Points Calculator - {serial}")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(500, 600)
        self.resize(540, 660)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.cfg = get_node_config(self.serial)
        self.setStyleSheet(VSCODE_THEME)
        self._init_ui()

    def _init_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(20, 20, 20, 20)
        vbox.setSpacing(14)

        # Header Title
        title_lbl = QLabel("Esports Kill & Placement Points")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f0f6fc;")
        vbox.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Configure kill multipliers and placement rank points.\n"
            "Calculated leaderboards will be appended to Discord Webhook embeds."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.4;")
        vbox.addWidget(desc_lbl)

        # Enable Toggle Row
        toggle_frame = QFrame()
        toggle_frame.setStyleSheet("QFrame { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        t_layout = QHBoxLayout(toggle_frame)
        t_layout.setContentsMargins(14, 10, 14, 10)

        self.enable_chk = QCheckBox("Enable Esports Points in Discord Embeds")
        self.enable_chk.setChecked(bool(self.cfg.get("esportsMode", False)))
        self.enable_chk.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 12px;")
        t_layout.addWidget(self.enable_chk)
        t_layout.addStretch()
        vbox.addWidget(toggle_frame)

        # Kill Points Row
        kill_row = QHBoxLayout()
        kill_lbl = QLabel("Points Per Kill (Multiplier):")
        kill_lbl.setStyleSheet("color: #c9d1d9; font-size: 12px; font-weight: 600;")
        self.kill_spin = QSpinBox()
        self.kill_spin.setRange(0, 50)
        self.kill_spin.setValue(int(self.cfg.get("esportsKillPoints", 1)))
        self.kill_spin.setFixedWidth(90)
        self.kill_spin.setFixedHeight(30)
        kill_row.addWidget(kill_lbl)
        kill_row.addStretch()
        kill_row.addWidget(self.kill_spin)
        vbox.addLayout(kill_row)

        # Rank Table
        table_title = QLabel("Placement Points Distribution (Rank 1 - 12):")
        table_title.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        vbox.addWidget(table_title)

        self.table = QTableWidget(12, 2)
        self.table.setHorizontalHeaderLabels(["Placement Rank", "Points Awarded"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 150)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #0b0e14; gridline-color: #21262d; border: 1px solid #30363d; border-radius: 6px; }"
            "QHeaderView::section { background-color: #161b22; color: #8b949e; font-weight: 600; font-size: 11px; padding: 6px 8px; border: none; border-bottom: 1px solid #30363d; }"
        )

        saved_pts = self.cfg.get("esportsPlacementPoints", DEFAULT_PLACEMENTS)
        if not isinstance(saved_pts, list) or len(saved_pts) < 12:
            saved_pts = DEFAULT_PLACEMENTS

        self.spinners: List[QSpinBox] = []
        for i in range(12):
            self.table.setRowHeight(i, 32)
            rank_item = QTableWidgetItem(f"  Rank #{i + 1}")
            rank_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(i, 0, rank_item)

            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(int(saved_pts[i]) if i < len(saved_pts) else 0)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setFixedWidth(120)
            spin.setFixedHeight(28)
            self.spinners.append(spin)
            self.table.setCellWidget(i, 1, spin)

        vbox.addWidget(self.table, 1)

        # Test Screenshot & Preview Section
        preview_box = QFrame()
        preview_box.setStyleSheet("QFrame { background-color: #0b0e14; border: 1px solid #262c36; border-radius: 6px; }")
        pb_layout = QVBoxLayout(preview_box)
        pb_layout.setContentsMargins(12, 10, 12, 10)
        pb_layout.setSpacing(8)

        pb_top = QHBoxLayout()
        pb_title = QLabel("LIVE SCREENSHOT OCR TESTER")
        pb_title.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        pb_top.addWidget(pb_title)
        pb_top.addStretch()

        self.test_img_btn = QPushButton("Upload & Test Screenshot")
        self.test_img_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
            }
        """)
        self.test_img_btn.clicked.connect(self._test_screenshot)
        pb_top.addWidget(self.test_img_btn)
        pb_layout.addLayout(pb_top)

        from PyQt6.QtWidgets import QTextEdit
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Click 'Upload & Test Screenshot' to test a Free Fire scoreboard image with current points...")
        self.preview_text.setFixedHeight(140)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #07090d;
                color: #58a6ff;
                border: 1px solid #1f2937;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.3;
                padding: 6px;
            }
        """)
        pb_layout.addWidget(self.preview_text)
        vbox.addWidget(preview_box)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        reset_btn = QPushButton("Reset Standard (12-9-8...)")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #f0f6fc;
            }
        """)
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

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

        save_btn = QPushButton("Save Points")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        vbox.addLayout(btn_row)

    def _test_screenshot(self):
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtCore import QThread, pyqtSignal
        from PIL import Image

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Scoreboard Screenshot to Test",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path or not os.path.exists(file_path):
            return

        self.preview_text.setPlainText("Processing screenshot with PaddleOCR engine in background... Please wait...")
        self.test_img_btn.setEnabled(False)

        pts = [spin.value() for spin in self.spinners]
        kill_pts = self.kill_spin.value()
        c_y = float(self.cfg.get("cropY", 0.22) or 0.22)
        c_h = float(self.cfg.get("cropH", 0.66) or 0.66)

        class EsportsOcrWorker(QThread):
            finished = pyqtSignal(str)
            error = pyqtSignal(str)

            def run(self):
                try:
                    img = Image.open(file_path)
                    from src.core.esports_calculator import parse_esports_scoreboard
                    result_table = parse_esports_scoreboard(
                        img,
                        kill_multiplier=kill_pts,
                        placement_points=pts,
                        crop_y=c_y,
                        crop_h=c_h
                    )
                    self.finished.emit(result_table)
                except Exception as e:
                    self.error.emit(str(e))

        self._worker = EsportsOcrWorker(self)
        self._worker.finished.connect(lambda out: self._on_test_finished(out))
        self._worker.error.connect(lambda err: self._on_test_error(err))
        self._worker.start()

    def _on_test_finished(self, text: str):
        self.preview_text.setPlainText(text)
        self.test_img_btn.setEnabled(True)

    def _on_test_error(self, err: str):
        self.preview_text.setPlainText(f"Error executing OCR test:\n{err}")
        self.test_img_btn.setEnabled(True)

    def _reset_defaults(self):
        for idx, val in enumerate(DEFAULT_PLACEMENTS):
            if idx < len(self.spinners):
                self.spinners[idx].setValue(val)
        self.kill_spin.setValue(1)

    def _save(self):
        pts = [spin.value() for spin in self.spinners]
        self.cfg["esportsMode"] = self.enable_chk.isChecked()
        self.cfg["esportsKillPoints"] = self.kill_spin.value()
        self.cfg["esportsPlacementPoints"] = pts
        save_node_config(self.serial, self.cfg)
        self.accept()
