# -*- coding: utf-8 -*-
import os
import time
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QCursor

from src.core.match_database import MatchDatabase
from src.ui.theme import VSCODE_THEME


class MatchPreviewModal(QDialog):
    """Full-size high-definition viewer for a match capture"""
    def __init__(self, image_path: str, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(760, 500)
        self.resize(1000, 620)
        self.setStyleSheet(VSCODE_THEME)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header with title and close button
        header = QHBoxLayout()
        header_lbl = QLabel(title)
        header_lbl.setStyleSheet("color: #f0f6fc; font-size: 15px; font-weight: 700;")
        header.addWidget(header_lbl)
        header.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("HeaderRefreshBtn")
        close_btn.setFixedHeight(30)
        close_btn.clicked.connect(self.accept)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Large image canvas
        canvas = QLabel()
        canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas.setStyleSheet("background-color: #07090d; border: 1px solid #21262d; border-radius: 6px;")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            scaled = pixmap.scaled(960, 520, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            canvas.setPixmap(scaled)
        else:
            canvas.setText("Capture image not found on disk")
            canvas.setStyleSheet("color: #6e7681; font-size: 14px;")
        layout.addWidget(canvas, 1)


class MatchHistoryDialog(QDialog):
    """
    Obsidian-styled Match History Browser:
    - Shows match count & last match timestamp stats
    - Responsive grid of match screenshot cards
    - Click any card to inspect full high-definition screenshot
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Booyah - Match History")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        self.setMinimumSize(880, 560)
        self.resize(1060, 680)
        self.setStyleSheet(VSCODE_THEME)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # 1. Header Toolbar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("MATCH HISTORY ARCHIVE")
        title.setStyleSheet("color: #f0f6fc; font-size: 16px; font-weight: 700; letter-spacing: 0.8px;")
        subtitle = QLabel("Browse auto-captured scoreboards and match completion results")
        subtitle.setStyleSheet("color: #8b949e; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)

        header.addStretch()

        self.stat_matches = QLabel("0 MATCHES")
        self.stat_matches.setObjectName("BadgeSuccess")
        header.addWidget(self.stat_matches)

        clear_btn = QPushButton("Clear History")
        clear_btn.setObjectName("HeaderRefreshBtn")
        clear_btn.setFixedHeight(30)
        clear_btn.setToolTip("Delete all saved match captures and database logs")
        clear_btn.clicked.connect(self._clear_all_matches)
        header.addWidget(clear_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("HeaderRefreshBtn")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.load_matches)
        header.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("HeaderRefreshBtn")
        close_btn.setFixedHeight(30)
        close_btn.clicked.connect(self.accept)
        header.addWidget(close_btn)

        layout.addLayout(header)

        # 2. Scrollable Cards Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent;")

        self.cards_container = QWidget()
        self.grid_layout = QGridLayout(self.cards_container)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, 1)

        self.load_matches()

    def load_matches(self):
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        matches = MatchDatabase.get().get_matches(limit=50)
        self.stat_matches.setText(f"{len(matches)} MATCHES")

        if not matches:
            empty_lbl = QLabel("No match captures found.\nMatches will appear here as they are detected.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #6e7681; font-size: 14px; padding: 100px; line-height: 1.6;")
            self.grid_layout.addWidget(empty_lbl, 0, 0)
            return

        cols = 3
        for idx, m in enumerate(matches):
            card = self._create_match_card(m)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def _create_match_card(self, match_data: dict) -> QFrame:
        card = QFrame()
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #262c36;
                border-radius: 6px;
            }
            QFrame:hover {
                border-color: #f43f5e;
                background-color: #1c2128;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Image preview
        img_lbl = QLabel()
        img_lbl.setFixedHeight(140)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("background-color: #07090d; border-radius: 4px;")

        path = match_data.get("capture_path", "")
        if os.path.exists(path):
            pix = QPixmap(path)
            thumb = pix.scaled(280, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            img_lbl.setPixmap(thumb)
        else:
            img_lbl.setText("No Image")
            img_lbl.setStyleSheet("color: #6e7681; font-size: 11px;")

        layout.addWidget(img_lbl)

        # Metadata Row
        alias = match_data.get("alias") or match_data.get("node_id") or "Emulator"
        mode = match_data.get("mode") or "MATCH"
        ts = match_data.get("timestamp", 0) / 1000.0
        time_str = time.strftime("%Y-%m-%d %I:%M %p", time.localtime(ts)) if ts > 0 else "Unknown"

        meta_row = QHBoxLayout()
        name_lbl = QLabel(f"{alias} ({mode})")
        name_lbl.setStyleSheet("color: #f0f6fc; font-weight: 600; font-size: 12px;")
        meta_row.addWidget(name_lbl)
        meta_row.addStretch()

        del_btn = QPushButton("X")
        del_btn.setFixedSize(24, 24)
        del_btn.setToolTip("Delete this match record")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #f85149;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(248, 81, 73, 0.15);
                border-color: #f85149;
            }
        """)
        match_id = match_data.get("id")
        del_btn.clicked.connect(lambda: self._delete_single_match(match_id))
        meta_row.addWidget(del_btn)

        layout.addLayout(meta_row)

        time_lbl = QLabel(f"Recorded: {time_str}")
        time_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(time_lbl)

        winners_val = match_data.get("winners") or ""
        if winners_val:
            win_lbl = QLabel(f"[Winner] {winners_val}")
            win_lbl.setWordWrap(True)
            win_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600; padding-top: 2px;")
            layout.addWidget(win_lbl)

        def on_click(e):
            MatchPreviewModal(path, f"{alias} - {time_str}", self).exec()

        img_lbl.mousePressEvent = on_click
        return card

    def _delete_single_match(self, match_id: int):
        reply = QMessageBox.question(
            self, "Delete Match Record",
            "Are you sure you want to delete this match record and screenshot?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            MatchDatabase.get().delete_match(match_id)
            self.load_matches()

    def _clear_all_matches(self):
        reply = QMessageBox.warning(
            self, "Clear Entire Match History",
            "Are you sure you want to delete ALL match history records and screenshots?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            MatchDatabase.get().clear_all_matches()
            self.load_matches()
