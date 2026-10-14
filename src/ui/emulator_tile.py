# -*- coding: utf-8 -*-
import io
from typing import Optional
from PIL import Image
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QCursor, QColor

from src.core.config_manager import get_node_config

GLOW_COLORS = {
    "IDLE": QColor(35, 39, 48, 140),
    "IN_GAME": QColor(6, 182, 212, 180),          # Neon Cyan
    "RESULT_SCREEN": QColor(16, 185, 129, 210),   # Emerald Victory
    "MATCH": QColor(16, 185, 129, 210),           # Emerald Victory
    "WAIT": QColor(245, 158, 11, 190),            # Amber Settling
    "SLEEP": QColor(168, 85, 247, 180),           # Royal Purple
}


class EmulatorTile(QFrame):
    """
    Obsidian Tile:
    - Display Name & Phase Glow Badge in header
    - Crisp 16:9 Screen Canvas with dynamic ambient glow radiating behind the preview
    """
    tile_clicked = pyqtSignal(str)

    def __init__(self, serial: str, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.is_selected = False
        self.current_phase = "IDLE"

        self.setObjectName("MinimalTile")
        self.setProperty("phase", "IDLE")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(285)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 1. Header: Instance Name + Glowing Phase Badge
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        cfg = get_node_config(serial)
        display_name = cfg.get("customName") or serial
        self.name_lbl = QLabel(display_name)
        self.name_lbl.setStyleSheet("color: #f0f6fc; font-size: 13px; font-weight: 700;")
        header_row.addWidget(self.name_lbl)

        header_row.addStretch()

        self.phase_badge = QLabel("IDLE")
        self.phase_badge.setStyleSheet(
            "font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
            "padding: 2px 8px; border-radius: 10px; "
            "background-color: #21262d; color: #8b949e; border: 1px solid #30363d;"
        )
        header_row.addWidget(self.phase_badge)
        layout.addLayout(header_row)

        # 2. Screen Canvas (240p height: 426x240 for 16:9)
        self.preview_lbl = QLabel()
        self.preview_lbl.setObjectName("ScreenCanvas")
        self.preview_lbl.setProperty("phase", "IDLE")
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setText("Connecting...")
        self.preview_lbl.setStyleSheet("color: #6e7681; font-size: 12px;")
        self.preview_lbl.setFixedHeight(240)

        # Ambient Glow Effect radiating behind the preview canvas
        self.glow_effect = QGraphicsDropShadowEffect(self)
        self.glow_effect.setBlurRadius(20)
        self.glow_effect.setOffset(0, 0)
        self.glow_effect.setColor(GLOW_COLORS["IDLE"])
        self.preview_lbl.setGraphicsEffect(self.glow_effect)

        layout.addWidget(self.preview_lbl)

    def mousePressEvent(self, event):
        self.tile_clicked.emit(self.serial)
        super().mousePressEvent(event)

    def set_selected(self, active: bool):
        self.is_selected = active
        self.setObjectName("MinimalTileSelected" if active else "MinimalTile")
        self._refresh_styles()

    def set_phase(self, phase: str, label: Optional[str] = None):
        self.current_phase = phase
        badge_text = label or phase.replace("_", " ")
        self.phase_badge.setText(badge_text)

        PHASE_BADGE_STYLES = {
            "IDLE":          "background-color: #21262d; color: #8b949e; border: 1px solid #30363d;",
            "IN_GAME":       "background-color: rgba(56, 189, 248, 0.16); color: #38bdf8; border: 1px solid #0284c7;",
            "RESULT_SCREEN": "background-color: rgba(46, 160, 67, 0.20); color: #3fb950; border: 1px solid #2ea043;",
            "MATCH":         "background-color: rgba(46, 160, 67, 0.20); color: #3fb950; border: 1px solid #2ea043;",
            "WAIT":          "background-color: rgba(210, 153, 34, 0.18); color: #d29922; border: 1px solid #bb8009;",
            "SLEEP":         "background-color: rgba(188, 140, 255, 0.18); color: #bc8cff; border: 1px solid #8957e5;",
        }
        base_badge_style = (
            "font-size: 10px; font-weight: 700; letter-spacing: 0.6px; "
            "padding: 2px 8px; border-radius: 10px; "
        )
        phase_extra = PHASE_BADGE_STYLES.get(phase, PHASE_BADGE_STYLES["IDLE"])
        self.phase_badge.setStyleSheet(base_badge_style + phase_extra)

        self.preview_lbl.setProperty("phase", phase)
        self.setProperty("class", f"TilePhase-{phase}")

        glow_color = GLOW_COLORS.get(phase, GLOW_COLORS["IDLE"])
        self.glow_effect.setColor(glow_color)
        if phase in ("IN_GAME", "RESULT_SCREEN", "MATCH", "WAIT", "SLEEP"):
            self.glow_effect.setBlurRadius(28)
        else:
            self.glow_effect.setBlurRadius(16)

        self._refresh_styles()

    def _refresh_styles(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.preview_lbl.style().unpolish(self.preview_lbl)
        self.preview_lbl.style().polish(self.preview_lbl)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_preview()

    def _update_scaled_preview(self):
        if hasattr(self, '_orig_pixmap') and self._orig_pixmap and not self._orig_pixmap.isNull():
            lbl_w = self.preview_lbl.width()
            lbl_h = self.preview_lbl.height()
            if lbl_w > 10 and lbl_h > 10:
                scaled = self._orig_pixmap.scaled(
                    lbl_w, lbl_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_lbl.setPixmap(scaled)

    def update_name(self, name: str):
        self.name_lbl.setText(name if name else self.serial)

    def update_preview(self, pil_image: Image.Image):
        if not pil_image:
            return
        img_bytes = io.BytesIO()
        thumb = pil_image.copy()
        thumb.thumbnail((426, 240))
        thumb.save(img_bytes, format='JPEG', quality=90)
        qimg = QImage.fromData(img_bytes.getvalue())
        self._orig_pixmap = QPixmap.fromImage(qimg)
        self._update_scaled_preview()
