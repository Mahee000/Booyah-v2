# -*- coding: utf-8 -*-
"""
Booyah v2 Obsidian Studio Design System
Professional Dark Theme optimized for Windows PyQt6.
- Zero text clipping with dynamic layout spacing.
- Scoped selectors preventing QFormLayout & dialog bleed.
- Native Windows typography (Segoe UI) with high-DPI clarity.
- Crisp vector arrow icons for spinboxes and comboboxes.
"""
import os

_ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets")).replace("\\", "/")
_SPIN_UP = f"{_ASSETS_DIR}/spin_arrow_up.png"
_SPIN_DOWN = f"{_ASSETS_DIR}/spin_arrow_down.png"
_SPIN_UP_HOVER = f"{_ASSETS_DIR}/spin_arrow_up_hover.png"
_SPIN_DOWN_HOVER = f"{_ASSETS_DIR}/spin_arrow_down_hover.png"
_COMBO_DOWN = f"{_ASSETS_DIR}/combo_arrow_down.png"
_COMBO_DOWN_HOVER = f"{_ASSETS_DIR}/combo_arrow_down_hover.png"

VSCODE_THEME = f"""
/* ==========================================================================
   GLOBAL RESET & DEFAULTS
   ========================================================================== */
QWidget {{
    font-family: "Segoe UI", "Segoe UI Semibold", "Segoe UI Symbol", Arial, sans-serif;
    font-size: 12px;
    color: #c9d1d9;
    outline: none;
}}

QMainWindow, QDialog, QWidget#CentralWidget {{
    background-color: #0b0e14;
    color: #c9d1d9;
}}

/* Tooltips */
QToolTip {{
    background-color: #1a1e26;
    color: #f0f6fc;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 11px;
}}

/* ==========================================================================
   HEADER BAR
   ========================================================================== */
QFrame#HeaderFrame {{
    background-color: #0d1117;
    border-bottom: 1px solid #21262d;
    padding: 8px 16px;
}}

QLabel#HeaderTitle {{
    color: #f8fafc;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 1.2px;
}}

/* Badges */
QLabel#BadgeNeutral {{
    background-color: #161b22;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
}}

QLabel#BadgeSuccess {{
    background-color: rgba(46, 160, 67, 0.15);
    color: #3fb950;
    border: 1px solid rgba(46, 160, 67, 0.4);
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
}}

/* Header Buttons */
QPushButton#HeaderRefreshBtn {{
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 5px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
}}

QPushButton#HeaderRefreshBtn:hover {{
    background-color: #21262d;
    color: #ffffff;
    border-color: #f43f5e;
}}

QPushButton#HeaderRefreshBtn:pressed {{
    background-color: #2d333b;
}}

/* ==========================================================================
   INPUTS & FORM CONTROLS
   ========================================================================== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: #0d1117;
    border: 1.5px solid #3b4352;
    border-radius: 6px;
    padding: 5px 10px;
    color: #ffffff;
    font-size: 12px;
    font-weight: 500;
    selection-background-color: #e11d48;
    selection-color: #ffffff;
}}

QSpinBox QLineEdit, QDoubleSpinBox QLineEdit {{
    background: transparent;
    color: #ffffff;
    border: none;
    padding: 0px;
}}

QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: #64748b;
    background-color: #12161f;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1.5px solid #f43f5e;
    background-color: #151a24;
    color: #ffffff;
}}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: #080a0f;
    color: #4b5563;
    border-color: #1f242d;
}}

/* ComboBox Dropdown */
QComboBox {{
    padding-right: 28px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #3b4352;
    background-color: #161b22;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}

QComboBox::drop-down:hover {{
    background-color: #21262d;
}}

QComboBox::down-arrow {{
    image: url({_COMBO_DOWN});
    width: 12px;
    height: 12px;
}}

QComboBox::down-arrow:hover {{
    image: url({_COMBO_DOWN_HOVER});
}}

QComboBox QAbstractItemView {{
    background-color: #161b22;
    border: 1.5px solid #3b4352;
    border-radius: 6px;
    selection-background-color: #e11d48;
    selection-color: #ffffff;
    color: #f0f6fc;
    padding: 4px;
    outline: none;
}}

/* SpinBox Up/Down Controls */
QSpinBox, QDoubleSpinBox {{
    padding-right: 26px;
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    height: 14px;
    background-color: #1c2128;
    border-left: 1px solid #3b4352;
    border-bottom: 1px solid #3b4352;
    border-top-right-radius: 5px;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color: #30363d;
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    height: 14px;
    background-color: #1c2128;
    border-left: 1px solid #3b4352;
    border-bottom-right-radius: 5px;
}}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: #30363d;
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_SPIN_UP});
    width: 10px;
    height: 10px;
}}

QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{
    image: url({_SPIN_UP_HOVER});
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_SPIN_DOWN});
    width: 10px;
    height: 10px;
}}

QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{
    image: url({_SPIN_DOWN_HOVER});
}}

/* Checkbox */
QCheckBox {{
    spacing: 8px;
    color: #c9d1d9;
    font-size: 12px;
    font-weight: 500;
    background-color: transparent;
}}

QCheckBox:hover {{
    color: #f0f6fc;
}}

QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1px solid #30363d;
    background-color: #161b22;
}}

QCheckBox::indicator:hover {{
    border-color: #f43f5e;
}}

QCheckBox::indicator:checked {{
    background-color: #e11d48;
    border-color: #e11d48;
}}

/* ==========================================================================
   BUTTONS
   ========================================================================== */
QPushButton {{
    background-color: #1a1e26;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: #222731;
    color: #ffffff;
    border-color: #484f58;
}}

QPushButton:pressed {{
    background-color: #2d333f;
}}

QPushButton:disabled {{
    background-color: #111419;
    color: #484f58;
    border-color: #21262d;
}}

/* Primary Crimson Button */
QPushButton#PrimaryBtn {{
    background-color: #be123c;
    border: 1px solid #e11d48;
    color: #ffffff;
    font-weight: 700;
    padding: 6px 16px;
}}

QPushButton#PrimaryBtn:hover {{
    background-color: #e11d48;
    border-color: #fb7185;
}}

QPushButton#PrimaryBtn:pressed {{
    background-color: #9f1239;
}}

/* Danger / Stop Button */
QPushButton#DangerBtn {{
    background-color: #4c0519;
    border: 1px solid #9f1239;
    color: #fecdd3;
    font-weight: 700;
    padding: 6px 16px;
}}

QPushButton#DangerBtn:hover {{
    background-color: #881337;
    border-color: #f43f5e;
}}

QPushButton#DangerBtn:pressed {{
    background-color: #350311;
}}

/* Save Preset Button */
QPushButton#SaveBtn {{
    background-color: #211418;
    border: 1px solid #be123c;
    color: #fb7185;
    font-weight: 600;
    padding: 6px 16px;
}}

QPushButton#SaveBtn:hover {{
    background-color: #be123c;
    color: #ffffff;
}}

/* ==========================================================================
   CARDS & PANELS
   ========================================================================== */
QFrame#SidebarFrame {{
    background-color: #12151b;
    border-left: 1px solid #21262d;
}}

QFrame#MinimalTile {{
    background-color: #12151b;
    border: 1px solid #21262d;
    border-radius: 8px;
}}

QFrame#MinimalTile:hover {{
    border-color: #3b4352;
    background-color: #161a22;
}}

QFrame#MinimalTileSelected {{
    background-color: #1a1317;
    border: 2px solid #e11d48;
    border-radius: 8px;
}}

/* Screen Canvas */
QLabel#ScreenCanvas {{
    background-color: #07090d;
    border: 1px solid #1a1e26;
    border-radius: 6px;
}}

/* ==========================================================================
   SCROLLBARS & SPLITTERS
   ========================================================================== */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollBar:vertical {{
    border: none;
    background: #0b0e14;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: #21262d;
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #30363d;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0px;
    background: none;
    border: none;
}}

QScrollBar:horizontal {{
    border: none;
    background: #0b0e14;
    height: 8px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: #21262d;
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #30363d;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0px;
    background: none;
    border: none;
}}

QSplitter::handle {{
    background-color: #21262d;
}}

QSplitter::handle:hover {{
    background-color: #e11d48;
}}

/* ==========================================================================
   TABLES & STATUS BAR
   ========================================================================== */
QTableWidget {{
    background-color: #0d1117;
    gridline-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #c9d1d9;
    selection-background-color: #1e2430;
    selection-color: #ffffff;
}}

QHeaderView::section {{
    background-color: #161b22;
    color: #8b949e;
    font-weight: 600;
    font-size: 11px;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #30363d;
}}

QStatusBar {{
    background-color: #0d1117;
    border-top: 1px solid #21262d;
    color: #8b949e;
    font-size: 11px;
    padding: 4px 16px;
}}
"""
