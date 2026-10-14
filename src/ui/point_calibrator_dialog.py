# -*- coding: utf-8 -*-
import os
from typing import Optional, Tuple
from PIL import Image
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QFrame
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QRect
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen

from src.ui.theme import VSCODE_THEME


class PointPickCanvas(QLabel):
    coords_selected = pyqtSignal(float, float)

    def __init__(self, pil_image: Image.Image, initial_coords: Optional[Tuple[float, float]] = None, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #07090d; border: 1px solid #21262d; border-radius: 6px;")
        self.pil_image = pil_image
        self.orig_w, self.orig_h = pil_image.size
        self.picked_nx: Optional[float] = initial_coords[0] if initial_coords else None
        self.picked_ny: Optional[float] = initial_coords[1] if initial_coords else None
        self._pixmap_orig: Optional[QPixmap] = None
        self._load_image()

    def _load_image(self):
        img_rgb = self.pil_image.convert("RGBA")
        data = img_rgb.tobytes("raw", "RGBA")
        qim = QImage(data, self.pil_image.width, self.pil_image.height, QImage.Format.Format_RGBA8888)
        self._pixmap_orig = QPixmap.fromImage(qim)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.picked_nx is not None and self.picked_ny is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            disp_rect = self._get_image_display_rect()
            px = disp_rect.x() + int(self.picked_nx * disp_rect.width())
            py = disp_rect.y() + int(self.picked_ny * disp_rect.height())

            pen = QPen(QColor("#f43f5e"), 3)
            painter.setPen(pen)
            painter.drawEllipse(QPoint(px, py), 14, 14)
            painter.drawLine(px - 22, py, px + 22, py)
            painter.drawLine(px, py - 22, px, py + 22)
            painter.end()

    def _get_image_display_rect(self):
        if not self._pixmap_orig or self._pixmap_orig.isNull():
            return self.rect()
        scaled_size = self._pixmap_orig.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - scaled_size.width()) // 2
        y = (self.height() - scaled_size.height()) // 2
        return QRect(x, y, scaled_size.width(), scaled_size.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap_orig:
            scaled = self._pixmap_orig.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            disp_rect = self._get_image_display_rect()
            if disp_rect.contains(event.pos()):
                rel_x = event.pos().x() - disp_rect.x()
                rel_y = event.pos().y() - disp_rect.y()
                self.picked_nx = max(0.0, min(1.0, rel_x / disp_rect.width()))
                self.picked_ny = max(0.0, min(1.0, rel_y / disp_rect.height()))
                self.coords_selected.emit(self.picked_nx, self.picked_ny)
                self.update()


class PointCalibratorDialog(QDialog):
    """Visual coordinate picker on emulator screenshot with preloaded point support."""
    def __init__(self, frame: Image.Image, title: str = "Pick Coordinate", initial_coords: Optional[Tuple[float, float]] = None, parent=None):
        super().__init__(parent)
        self.selected_coords: Tuple[float, float] = initial_coords if initial_coords else (0.5, 0.5)
        self.setWindowTitle(title)
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(820, 540)
        self.resize(900, 600)
        self.setStyleSheet(VSCODE_THEME)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header
        top_row = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #f0f6fc; font-size: 15px; font-weight: 700;")
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        if initial_coords:
            self.coords_lbl = QLabel(f"Current Point: X: {initial_coords[0]*100:.1f}%  |  Y: {initial_coords[1]*100:.1f}% (Click to move)")
        else:
            self.coords_lbl = QLabel("Click anywhere on the preview to choose tap position")
        self.coords_lbl.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.coords_lbl)
        layout.addLayout(top_row)

        self.canvas = PointPickCanvas(frame, initial_coords=initial_coords, parent=self)
        self.canvas.coords_selected.connect(self._on_point_picked)
        layout.addWidget(self.canvas, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                padding: 6px 16px;
                border-radius: 5px;
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

        save_btn = QPushButton("Select Point")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _on_point_picked(self, nx: float, ny: float):
        self.selected_coords = (nx, ny)
        self.coords_lbl.setText(f"Selected: X: {nx*100:.1f}%  |  Y: {ny*100:.1f}%")
