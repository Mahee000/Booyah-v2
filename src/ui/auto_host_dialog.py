# -*- coding: utf-8 -*-
import os
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QFrame, QScrollArea,
    QSpinBox, QDoubleSpinBox, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PIL import Image

from src.core.emulator_service import EmulatorService
from src.core.config_manager import get_node_config, save_node_config
from src.ui.theme import VSCODE_THEME


class AutoHostStepRow(QFrame):
    """Single step card inside the sequence builder."""
    delete_requested = pyqtSignal(int)
    move_up_requested = pyqtSignal(int)
    move_down_requested = pyqtSignal(int)
    test_requested = pyqtSignal(int)
    calibrate_requested = pyqtSignal(int, str)  # index, type ('click', 'slideStart', 'slideEnd')

    def __init__(self, index: int, step_data: Dict[str, Any], is_first: bool, is_last: bool, parent=None):
        super().__init__(parent)
        self.index = index
        self.step_data = step_data
        self.setObjectName("StepCard")
        self.setStyleSheet("""
            QFrame#StepCard {
                background-color: #161b22;
                border: 1px solid #262c36;
                border-radius: 6px;
            }
        """)
        self._init_ui(is_first, is_last)

    def _init_ui(self, is_first: bool, is_last: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header with step title and action buttons
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        stype = self.step_data.get("type", "click")
        type_labels = {
            "click": "Click Target",
            "slide": "Slide / Swipe Path",
            "text": "Keyboard Input (Password/Text)"
        }
        title_lbl = QLabel(f"Step {self.index + 1}: {type_labels.get(stype, stype)}")
        title_lbl.setStyleSheet("color: #f43f5e; font-weight: 700; font-size: 12px;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()

        _btn_nav = """
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
                border-color: #f43f5e;
            }
            QPushButton:disabled {
                background-color: #111419;
                color: #484f58;
                border-color: #21262d;
            }
        """

        up_btn = QPushButton("^")
        up_btn.setFixedSize(26, 26)
        up_btn.setEnabled(not is_first)
        up_btn.setStyleSheet(_btn_nav)
        up_btn.setToolTip("Move Step Up")
        up_btn.clicked.connect(lambda: self.move_up_requested.emit(self.index))
        header_row.addWidget(up_btn)

        down_btn = QPushButton("v")
        down_btn.setFixedSize(26, 26)
        down_btn.setEnabled(not is_last)
        down_btn.setStyleSheet(_btn_nav)
        down_btn.setToolTip("Move Step Down")
        down_btn.clicked.connect(lambda: self.move_down_requested.emit(self.index))
        header_row.addWidget(down_btn)

        test_btn = QPushButton("Test")
        test_btn.setFixedHeight(26)
        test_btn.setMinimumWidth(56)
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e1065;
                color: #d8b4fe;
                border: 1px solid #581c87;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #3b0764;
                border-color: #c084fc;
                color: #ffffff;
            }
        """)
        test_btn.setToolTip("Test this action on live emulator")
        test_btn.clicked.connect(lambda: self.test_requested.emit(self.index))
        header_row.addWidget(test_btn)

        del_btn = QPushButton("X")
        del_btn.setFixedSize(26, 26)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #3f1219;
                color: #fda4af;
                border: 1px solid #9f1239;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #881337;
                border-color: #f43f5e;
                color: #ffffff;
            }
        """)
        del_btn.setToolTip("Delete this step")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.index))
        header_row.addWidget(del_btn)

        layout.addLayout(header_row)

        _lbl_style = "font-size: 12px; color: #8b949e; font-weight: 500;"
        _pick_btn_style = """
            QPushButton {
                background-color: #10233d;
                color: #38bdf8;
                border: 1px solid #1e40af;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #1e3a8a;
                border-color: #60a5fa;
                color: #ffffff;
            }
        """

        if stype == "click":
            c_row = QHBoxLayout()
            c_row.setSpacing(8)

            lbl_x = QLabel("X %:")
            lbl_x.setStyleSheet(_lbl_style)
            c_row.addWidget(lbl_x)

            self.x_spin = QDoubleSpinBox()
            self.x_spin.setRange(0.0, 100.0)
            self.x_spin.setDecimals(1)
            self.x_spin.setSuffix("%")
            self.x_spin.setValue(float(self.step_data.get("x", 0.5)) * 100.0)
            self.x_spin.setFixedHeight(28)
            self.x_spin.setMinimumWidth(85)
            self.x_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            c_row.addWidget(self.x_spin)

            lbl_y = QLabel("Y %:")
            lbl_y.setStyleSheet(_lbl_style)
            c_row.addWidget(lbl_y)

            self.y_spin = QDoubleSpinBox()
            self.y_spin.setRange(0.0, 100.0)
            self.y_spin.setDecimals(1)
            self.y_spin.setSuffix("%")
            self.y_spin.setValue(float(self.step_data.get("y", 0.5)) * 100.0)
            self.y_spin.setFixedHeight(28)
            self.y_spin.setMinimumWidth(85)
            self.y_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            c_row.addWidget(self.y_spin)

            pick_btn = QPushButton("Pick Point")
            pick_btn.setFixedHeight(28)
            pick_btn.setStyleSheet(_pick_btn_style)
            pick_btn.clicked.connect(lambda: self.calibrate_requested.emit(self.index, "click"))
            c_row.addWidget(pick_btn)

            c_row.addStretch()
            layout.addLayout(c_row)

        elif stype == "slide":
            # Slide start coordinates
            s_row = QHBoxLayout()
            s_row.setSpacing(8)

            lbl_s = QLabel("Start:")
            lbl_s.setStyleSheet("font-size: 12px; color: #e2e8f0; font-weight: 600;")
            s_row.addWidget(lbl_s)

            lbl_sx = QLabel("X %:")
            lbl_sx.setStyleSheet(_lbl_style)
            s_row.addWidget(lbl_sx)

            self.sx_spin = QDoubleSpinBox()
            self.sx_spin.setRange(0.0, 100.0)
            self.sx_spin.setDecimals(1)
            self.sx_spin.setSuffix("%")
            self.sx_spin.setValue(float(self.step_data.get("startX", 0.5)) * 100.0)
            self.sx_spin.setFixedHeight(28)
            self.sx_spin.setMinimumWidth(80)
            self.sx_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            s_row.addWidget(self.sx_spin)

            lbl_sy = QLabel("Y %:")
            lbl_sy.setStyleSheet(_lbl_style)
            s_row.addWidget(lbl_sy)

            self.sy_spin = QDoubleSpinBox()
            self.sy_spin.setRange(0.0, 100.0)
            self.sy_spin.setDecimals(1)
            self.sy_spin.setSuffix("%")
            self.sy_spin.setValue(float(self.step_data.get("startY", 0.7)) * 100.0)
            self.sy_spin.setFixedHeight(28)
            self.sy_spin.setMinimumWidth(80)
            self.sy_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            s_row.addWidget(self.sy_spin)

            pick_start_btn = QPushButton("Pick Start")
            pick_start_btn.setFixedHeight(28)
            pick_start_btn.setStyleSheet(_pick_btn_style)
            pick_start_btn.clicked.connect(lambda: self.calibrate_requested.emit(self.index, "slideStart"))
            s_row.addWidget(pick_start_btn)

            s_row.addStretch()
            layout.addLayout(s_row)

            # Slide end coordinates
            e_row = QHBoxLayout()
            e_row.setSpacing(8)

            lbl_e = QLabel("End:")
            lbl_e.setStyleSheet("font-size: 12px; color: #e2e8f0; font-weight: 600;")
            e_row.addWidget(lbl_e)

            lbl_ex = QLabel("X %:")
            lbl_ex.setStyleSheet(_lbl_style)
            e_row.addWidget(lbl_ex)

            self.ex_spin = QDoubleSpinBox()
            self.ex_spin.setRange(0.0, 100.0)
            self.ex_spin.setDecimals(1)
            self.ex_spin.setSuffix("%")
            self.ex_spin.setValue(float(self.step_data.get("endX", 0.5)) * 100.0)
            self.ex_spin.setFixedHeight(28)
            self.ex_spin.setMinimumWidth(80)
            self.ex_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            e_row.addWidget(self.ex_spin)

            lbl_ey = QLabel("Y %:")
            lbl_ey.setStyleSheet(_lbl_style)
            e_row.addWidget(lbl_ey)

            self.ey_spin = QDoubleSpinBox()
            self.ey_spin.setRange(0.0, 100.0)
            self.ey_spin.setDecimals(1)
            self.ey_spin.setSuffix("%")
            self.ey_spin.setValue(float(self.step_data.get("endY", 0.3)) * 100.0)
            self.ey_spin.setFixedHeight(28)
            self.ey_spin.setMinimumWidth(80)
            self.ey_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
            e_row.addWidget(self.ey_spin)

            pick_end_btn = QPushButton("Pick End")
            pick_end_btn.setFixedHeight(28)
            pick_end_btn.setStyleSheet(_pick_btn_style)
            pick_end_btn.clicked.connect(lambda: self.calibrate_requested.emit(self.index, "slideEnd"))
            e_row.addWidget(pick_end_btn)

            e_row.addStretch()
            layout.addLayout(e_row)

        elif stype == "text":
            t_row = QHBoxLayout()
            t_row.setSpacing(8)

            lbl_txt = QLabel("Text / Password:")
            lbl_txt.setStyleSheet(_lbl_style)
            t_row.addWidget(lbl_txt)

            self.text_input = QLineEdit()
            self.text_input.setPlaceholderText("e.g. room password or room name")
            self.text_input.setText(str(self.step_data.get("text", "")))
            self.text_input.setFixedHeight(28)
            t_row.addWidget(self.text_input, 1)
            layout.addLayout(t_row)

        # Delay row
        d_row = QHBoxLayout()
        d_row.setSpacing(8)

        lbl_delay = QLabel("Delay After Step:")
        lbl_delay.setStyleSheet(_lbl_style)
        d_row.addWidget(lbl_delay)

        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 30.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setDecimals(1)
        self.delay_spin.setSuffix(" s")
        self.delay_spin.setValue(float(self.step_data.get("delay", 1.0) if self.step_data.get("delay") is not None else 1.0))
        self.delay_spin.setFixedWidth(100)
        self.delay_spin.setFixedHeight(28)
        self.delay_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        d_row.addWidget(self.delay_spin)

        d_row.addStretch()
        layout.addLayout(d_row)

    def get_data(self) -> Dict[str, Any]:
        stype = self.step_data.get("type", "click")
        data = {
            "type": stype,
            "delay": round(self.delay_spin.value(), 1)
        }
        if stype == "click":
            data["x"] = round(self.x_spin.value() / 100.0, 3)
            data["y"] = round(self.y_spin.value() / 100.0, 3)
        elif stype == "slide":
            data["startX"] = round(self.sx_spin.value() / 100.0, 3)
            data["startY"] = round(self.sy_spin.value() / 100.0, 3)
            data["endX"] = round(self.ex_spin.value() / 100.0, 3)
            data["endY"] = round(self.ey_spin.value() / 100.0, 3)
        elif stype == "text":
            data["text"] = self.text_input.text().strip()
        return data


class AutoHostDialog(QDialog):
    """
    Modal for Auto Room Creation Sequence Builder and Match Time Scheduler.
    Configures the macro sequence to automate hosting custom matches.
    """
    def __init__(self, serial: str, service: EmulatorService, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.service = service
        self.config = get_node_config(serial)
        
        # Load custom actions, or auto-inherit the mode's default room creation actions
        existing_actions = self.config.get("autoHostActions", [])
        if not existing_actions:
            from src.core.preset_service import get_default_room_actions_for_mode
            mode = self.config.get("mode", "LW")
            existing_actions = get_default_room_actions_for_mode(mode)

        self.actions: List[Dict[str, Any]] = list(existing_actions)

        self.setWindowTitle(f"Auto Host Sequence Builder - {serial}")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(640, 700)
        self.resize(680, 760)
        self.setStyleSheet(VSCODE_THEME)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header Title
        title_lbl = QLabel("Auto Host & Room Creation Builder")
        title_lbl.setStyleSheet("color: #f0f6fc; font-size: 16px; font-weight: 700;")
        layout.addWidget(title_lbl)

        desc = QLabel(
            "Define the ordered macro sequence of clicks, swipes, and text inputs to automatically create "
            "custom rooms on this emulator before matches begin."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        # Match Scheduler Card
        sched_card = QFrame()
        sched_card.setObjectName("SchedCard")
        sched_card.setStyleSheet("QFrame#SchedCard { background-color: #161b22; border: 1px solid #262c36; border-radius: 6px; }")
        s_layout = QVBoxLayout(sched_card)
        s_layout.setContentsMargins(14, 12, 14, 12)
        s_layout.setSpacing(10)

        s_title = QLabel("MATCH TIME SCHEDULER & MASTER EMULATOR")
        s_title.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        s_layout.addWidget(s_title)

        lead_row = QHBoxLayout()
        lead_row.setSpacing(10)
        lead_lbl = QLabel("Host Room Before Match:")
        lead_lbl.setStyleSheet("color: #c9d1d9; font-size: 12px; font-weight: 500;")
        lead_row.addWidget(lead_lbl)

        self.lead_time_spin = QSpinBox()
        self.lead_time_spin.setRange(1, 60)
        self.lead_time_spin.setSuffix(" min")
        self.lead_time_spin.setValue(int(self.config.get("autoHostLeadTime", 5) or 5))
        self.lead_time_spin.setFixedWidth(110)
        self.lead_time_spin.setFixedHeight(30)
        self.lead_time_spin.lineEdit().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lead_row.addWidget(self.lead_time_spin)
        lead_row.addStretch()
        s_layout.addLayout(lead_row)

        # Master Controller Emulator Row
        master_row = QHBoxLayout()
        master_row.setSpacing(10)
        master_lbl = QLabel("Master / Reward Emulator:")
        master_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 600;")
        master_row.addWidget(master_lbl)

        from PyQt6.QtWidgets import QComboBox
        self.master_combo = QComboBox()
        self.master_combo.addItem("None (Standalone Node)", "None")
        try:
            connected = self.service.get_connected_devices()
            for dev in connected:
                d_serial = dev["serial"]
                if d_serial != self.serial:
                    self.master_combo.addItem(f"{dev.get('alias', d_serial)} ({d_serial})", d_serial)
        except Exception:
            pass
        
        saved_master = self.config.get("autoHostMaster", "None")
        idx = self.master_combo.findData(saved_master)
        if idx >= 0:
            self.master_combo.setCurrentIndex(idx)
        self.master_combo.setFixedHeight(30)
        self.master_combo.setMinimumWidth(220)
        master_row.addWidget(self.master_combo)
        master_row.addStretch()
        s_layout.addLayout(master_row)

        sched_hint = QLabel(
            "When room creation completes, Room ID and Password will be automatically copied "
            "and synchronized to the selected Master Emulator via OCR."
        )
        sched_hint.setWordWrap(True)
        sched_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        s_layout.addWidget(sched_hint)

        layout.addWidget(sched_card)

        # Sequence Steps Container
        seq_label = QLabel("LOBBY CREATION SEQUENCE STEPS")
        seq_label.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700; letter-spacing: 0.8px;")
        layout.addWidget(seq_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: #0b0e14; border: 1px solid #21262d; border-radius: 6px;")

        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(10, 10, 10, 10)
        self.steps_layout.setSpacing(8)
        self.steps_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.steps_container)

        layout.addWidget(self.scroll_area, 1)

        # Add Step Buttons Row
        add_row = QHBoxLayout()
        add_row.setSpacing(8)

        _add_btn_style = """
            QPushButton {
                background-color: #1a1e26;
                color: #f0f6fc;
                border: 1px solid #30363d;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #222731;
                border-color: #f43f5e;
                color: #ffffff;
            }
        """

        add_click_btn = QPushButton("+ Add Click")
        add_click_btn.setFixedHeight(34)
        add_click_btn.setStyleSheet(_add_btn_style)
        add_click_btn.clicked.connect(lambda: self._add_step("click"))
        add_row.addWidget(add_click_btn, 1)

        add_slide_btn = QPushButton("+ Add Slide")
        add_slide_btn.setFixedHeight(34)
        add_slide_btn.setStyleSheet(_add_btn_style)
        add_slide_btn.clicked.connect(lambda: self._add_step("slide"))
        add_row.addWidget(add_slide_btn, 1)

        add_text_btn = QPushButton("+ Add Text")
        add_text_btn.setFixedHeight(34)
        add_text_btn.setStyleSheet(_add_btn_style)
        add_text_btn.clicked.connect(lambda: self._add_step("text"))
        add_row.addWidget(add_text_btn, 1)

        load_template_btn = QPushButton("Load Default Macro")
        load_template_btn.setFixedHeight(34)
        load_template_btn.setToolTip("Populate sequence with the default room creation macro for this game mode")
        load_template_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b1d0c;
                color: #fbbf24;
                border: 1px solid #854d0e;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #45290a;
                border-color: #facc15;
                color: #ffffff;
            }
        """)
        load_template_btn.clicked.connect(self._load_mode_template)
        add_row.addWidget(load_template_btn)

        layout.addLayout(add_row)

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

        save_btn = QPushButton("Save Sequence")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setFixedHeight(36)
        save_btn.clicked.connect(self._save_sequence)
        btn_row.addWidget(save_btn, 1)

        layout.addLayout(btn_row)

        self._render_steps()
        save_btn.setFocus()

    def _render_steps(self):
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.actions:
            empty_lbl = QLabel("No steps defined yet.\nClick '+ Add Click', '+ Add Slide', or '+ Add Text' above to build your sequence.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #6e7681; font-size: 12px; padding: 32px; line-height: 1.5;")
            self.steps_layout.addWidget(empty_lbl)
            return

        for idx, step_data in enumerate(self.actions):
            is_first = (idx == 0)
            is_last = (idx == len(self.actions) - 1)
            row = AutoHostStepRow(idx, step_data, is_first, is_last, self.steps_container)
            row.delete_requested.connect(self._delete_step)
            row.move_up_requested.connect(self._move_up_step)
            row.move_down_requested.connect(self._move_down_step)
            row.test_requested.connect(self._test_step)
            row.calibrate_requested.connect(self._calibrate_step)
            self.steps_layout.addWidget(row)

    def _sync_actions_from_ui(self):
        new_actions = []
        for i in range(self.steps_layout.count()):
            widget = self.steps_layout.itemAt(i).widget()
            if isinstance(widget, AutoHostStepRow):
                new_actions.append(widget.get_data())
        self.actions = new_actions

    def _add_step(self, step_type: str):
        self._sync_actions_from_ui()
        if step_type == "click":
            self.actions.append({"type": "click", "x": 0.5, "y": 0.5, "delay": 1.0})
        elif step_type == "slide":
            self.actions.append({"type": "slide", "startX": 0.5, "startY": 0.7, "endX": 0.5, "endY": 0.3, "delay": 1.0})
        elif step_type == "text":
            self.actions.append({"type": "text", "text": "", "delay": 1.0})
        self._render_steps()

    def _delete_step(self, index: int):
        self._sync_actions_from_ui()
        if 0 <= index < len(self.actions):
            self.actions.pop(index)
            self._render_steps()

    def _move_up_step(self, index: int):
        self._sync_actions_from_ui()
        if index > 0:
            self.actions[index], self.actions[index - 1] = self.actions[index - 1], self.actions[index]
            self._render_steps()

    def _move_down_step(self, index: int):
        self._sync_actions_from_ui()
        if index < len(self.actions) - 1:
            self.actions[index], self.actions[index + 1] = self.actions[index + 1], self.actions[index]
            self._render_steps()

    def _test_step(self, index: int):
        self._sync_actions_from_ui()
        if index < 0 or index >= len(self.actions):
            return
        step = self.actions[index]
        stype = step.get("type")
        if stype == "click":
            x = float(step.get("x", 0.5))
            y = float(step.get("y", 0.5))
            self.service.tap_normalized(self.serial, x, y)
        elif stype == "slide":
            sx = float(step.get("startX", 0.5))
            sy = float(step.get("startY", 0.5))
            ex = float(step.get("endX", 0.5))
            ey = float(step.get("endY", 0.5))
            self.service.swipe_normalized(self.serial, sx, sy, ex, ey, 600)
        elif stype == "text":
            text = str(step.get("text", ""))
            self.service.input_text(self.serial, text)

    def _calibrate_step(self, index: int, calib_target: str):
        frame = self.service.capture_frame(self.serial)
        if not frame:
            QMessageBox.warning(self, "Recapture Failed", f"Could not capture frame from {self.serial}.")
            return
        
        from src.ui.point_calibrator_dialog import PointCalibratorDialog
        step = self.actions[index] if index < len(self.actions) else {}
        init_c = None
        try:
            if calib_target == "click":
                init_c = (float(step.get("x", 0.5)), float(step.get("y", 0.5)))
            elif calib_target == "slideStart":
                init_c = (float(step.get("startX", 0.5)), float(step.get("startY", 0.5)))
            elif calib_target == "slideEnd":
                init_c = (float(step.get("endX", 0.5)), float(step.get("endY", 0.5)))
        except (ValueError, TypeError):
            init_c = None

        dlg = PointCalibratorDialog(frame, f"Pick Coordinate for Step {index + 1} ({calib_target})", initial_coords=init_c, parent=self)
        if dlg.exec():
            nx, ny = dlg.selected_coords
            self._sync_actions_from_ui()
            if index < len(self.actions):
                if calib_target == "click":
                    self.actions[index]["x"] = round(nx, 3)
                    self.actions[index]["y"] = round(ny, 3)
                elif calib_target == "slideStart":
                    self.actions[index]["startX"] = round(nx, 3)
                    self.actions[index]["startY"] = round(ny, 3)
                elif calib_target == "slideEnd":
                    self.actions[index]["endX"] = round(nx, 3)
                    self.actions[index]["endY"] = round(ny, 3)
                self._render_steps()

    def _load_mode_template(self):
        from src.core.preset_service import get_default_room_actions_for_mode
        import copy
        mode = self.config.get("mode", "LW")
        steps = get_default_room_actions_for_mode(mode)
        if not steps:
            # Fallback to Lone Wolf steps as base template
            from src.core.preset_service import LONE_WOLF_ROOM_CREATION_STEPS
            steps = LONE_WOLF_ROOM_CREATION_STEPS
        self.actions = [copy.deepcopy(step) for step in steps]
        self._render_steps()
        QMessageBox.information(
            self,
            "Template Loaded",
            f"Loaded {len(self.actions)}-step base room creation macro for {mode} mode.\nYou can now adjust the steps and save."
        )

    def _save_sequence(self):
        self._sync_actions_from_ui()
        self.config["autoHostActions"] = self.actions
        self.config["autoHostLeadTime"] = self.lead_time_spin.value()
        self.config["autoHostMaster"] = self.master_combo.currentData()
        save_node_config(self.serial, self.config)
        self.accept()
