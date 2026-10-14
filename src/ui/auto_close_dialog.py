# -*- coding: utf-8 -*-
import os
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QFrame, QDoubleSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PIL import Image

from src.core.emulator_service import EmulatorService
from src.core.config_manager import load_app_settings, save_app_setting
from src.ui.theme import VSCODE_THEME


class AutoCloseDialog(QDialog):
    """
    Modal for Auto Close Room Calibration.
    Configures the 3-step tap coordinates and delays:
    1. Close Room Button (Header Top-Right)
    2. Confirm Close Button (Dialog Center-Right)
    3. Extra Close Button (Fallback Backout)
    """
    def __init__(self, serial: str, service: EmulatorService, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.service = service
        self.settings = load_app_settings()

        self.setWindowTitle("Auto Close Room Settings")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(600, 560)
        self.resize(640, 600)
        self.setStyleSheet(VSCODE_THEME)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header Title
        title_lbl = QLabel("Auto Close Room Calibration")
        title_lbl.setStyleSheet("color: #f0f6fc; font-size: 16px; font-weight: 700;")
        layout.addWidget(title_lbl)

        desc = QLabel(
            "Calibrate the coordinates and delays for automated room closing after matches finish.\n"
            "Runs: Close Room  >  Confirm Close  >  Extra Close sequence."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        # Step 1: Close Room Button
        self.c_x, self.c_y, self.c_delay = self._create_calib_group(
            layout,
            "1. Close Room Button (Header Top-Right)",
            float(self.settings.get("closeRoomX", 0.982)) * 100.0,
            float(self.settings.get("closeRoomY", 0.046)) * 100.0,
            float(self.settings.get("closeRoomDelay", 8.0)),
            "closeRoom"
        )

        # Step 2: Confirm Close Button
        self.cf_x, self.cf_y, self.cf_delay = self._create_calib_group(
            layout,
            "2. Confirm Close Button (Dialog Center-Right)",
            float(self.settings.get("confirmCloseX", 0.873)) * 100.0,
            float(self.settings.get("confirmCloseY", 0.621)) * 100.0,
            float(self.settings.get("confirmCloseDelay", 4.0)),
            "confirmClose"
        )

        # Step 3: Extra Close Button
        self.e_x, self.e_y, self.e_delay = self._create_calib_group(
            layout,
            "3. Extra Close Button (Fallback Backout)",
            float(self.settings.get("extraCloseX", 0.975)) * 100.0,
            float(self.settings.get("extraCloseY", 0.033)) * 100.0,
            float(self.settings.get("extraCloseDelay", 2.0)),
            "extraClose"
        )

        layout.addStretch()

        # Bottom Bar: Cancel & Save
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 20px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Calibration")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setFixedHeight(36)
        save_btn.clicked.connect(self._save_settings)
        btn_row.addWidget(save_btn, 1)

        layout.addLayout(btn_row)

    def _create_calib_group(self, layout: QVBoxLayout, title: str, default_x: float, default_y: float, default_delay: float, group_key: str):
        card = QFrame()
        card.setObjectName("CalibCard")
        card.setStyleSheet("QFrame#CalibCard { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(10)

        header_row = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #f43f5e; font-size: 12px; font-weight: 700;")
        header_row.addWidget(lbl)
        header_row.addStretch()

        test_btn = QPushButton("Test Tap")
        test_btn.setFixedHeight(26)
        test_btn.setMinimumWidth(75)
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e1065;
                color: #d8b4fe;
                border: 1px solid #581c87;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #3b0764;
                border-color: #c084fc;
                color: #ffffff;
            }
        """)
        header_row.addWidget(test_btn)
        c_layout.addLayout(header_row)

        row = QHBoxLayout()
        row.setSpacing(8)

        _lbl_style = "font-size: 12px; color: #8b949e; font-weight: 500;"

        lbl_x = QLabel("X %:")
        lbl_x.setStyleSheet(_lbl_style)
        row.addWidget(lbl_x)

        spin_x = QDoubleSpinBox()
        spin_x.setRange(0.0, 100.0)
        spin_x.setDecimals(1)
        spin_x.setSuffix("%")
        spin_x.setValue(default_x)
        spin_x.setFixedHeight(28)
        spin_x.setMinimumWidth(80)
        spin_x.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row.addWidget(spin_x, 1)

        lbl_y = QLabel("Y %:")
        lbl_y.setStyleSheet(_lbl_style)
        row.addWidget(lbl_y)

        spin_y = QDoubleSpinBox()
        spin_y.setRange(0.0, 100.0)
        spin_y.setDecimals(1)
        spin_y.setSuffix("%")
        spin_y.setValue(default_y)
        spin_y.setFixedHeight(28)
        spin_y.setMinimumWidth(80)
        spin_y.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row.addWidget(spin_y, 1)

        pick_btn = QPushButton("Pick Point")
        pick_btn.setFixedHeight(28)
        pick_btn.setMinimumWidth(80)
        pick_btn.setStyleSheet("""
            QPushButton {
                background-color: #10233d;
                color: #38bdf8;
                border: 1px solid #1e40af;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #1e3a8a;
                border-color: #60a5fa;
                color: #ffffff;
            }
        """)
        pick_btn.clicked.connect(lambda: self._pick_point(spin_x, spin_y, title))
        row.addWidget(pick_btn)

        lbl_wait = QLabel("Wait (s):")
        lbl_wait.setStyleSheet(_lbl_style)
        row.addWidget(lbl_wait)

        spin_d = QDoubleSpinBox()
        spin_d.setRange(0.1, 60.0)
        spin_d.setSingleStep(0.5)
        spin_d.setDecimals(1)
        spin_d.setSuffix(" s")
        spin_d.setValue(default_delay)
        spin_d.setFixedWidth(85)
        spin_d.setFixedHeight(28)
        spin_d.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row.addWidget(spin_d)

        test_btn.clicked.connect(lambda: self._test_tap(spin_x.value() / 100.0, spin_y.value() / 100.0))

        c_layout.addLayout(row)
        layout.addWidget(card)

        return spin_x, spin_y, spin_d

    def _test_tap(self, nx: float, ny: float):
        if self.serial:
            self.service.tap_normalized(self.serial, nx, ny)

    def _pick_point(self, spin_x: QDoubleSpinBox, spin_y: QDoubleSpinBox, title: str):
        frame = self.service.capture_frame(self.serial)
        if not frame:
            QMessageBox.warning(self, "Recapture Failed", f"Could not capture frame from {self.serial}.")
            return
        
        from src.ui.point_calibrator_dialog import PointCalibratorDialog
        init_c = (spin_x.value() / 100.0, spin_y.value() / 100.0)
        dlg = PointCalibratorDialog(frame, f"Pick Coordinate - {title}", initial_coords=init_c, parent=self)
        if dlg.exec():
            nx, ny = dlg.selected_coords
            spin_x.setValue(round(nx * 100.0, 1))
            spin_y.setValue(round(ny * 100.0, 1))

    def _save_settings(self):
        save_app_setting("closeRoomX", round(self.c_x.value() / 100.0, 3))
        save_app_setting("closeRoomY", round(self.c_y.value() / 100.0, 3))
        save_app_setting("closeRoomDelay", round(self.c_delay.value(), 1))

        save_app_setting("confirmCloseX", round(self.cf_x.value() / 100.0, 3))
        save_app_setting("confirmCloseY", round(self.cf_y.value() / 100.0, 3))
        save_app_setting("confirmCloseDelay", round(self.cf_delay.value(), 1))

        save_app_setting("extraCloseX", round(self.e_x.value() / 100.0, 3))
        save_app_setting("extraCloseY", round(self.e_y.value() / 100.0, 3))
        save_app_setting("extraCloseDelay", round(self.e_delay.value(), 1))

        self.accept()
