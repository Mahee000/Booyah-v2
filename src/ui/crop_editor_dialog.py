# -*- coding: utf-8 -*-
import os
from typing import Optional, Tuple
from PIL import Image
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRubberBand, QWidget, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from src.core.emulator_service import EmulatorService
from src.core.config_manager import get_node_config, save_node_config
from src.core.preset_service import PresetService
from src.ui.theme import VSCODE_THEME


class InteractiveCropCanvas(QLabel):
    """
    Canvas widget that renders the emulator frame and allows
    interactive dragging to select a crop region.
    """
    crop_changed = pyqtSignal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #07090d; border: 1px solid #21262d; border-radius: 6px;")
        self.rubber_band: Optional[QRubberBand] = None
        self.origin = QPoint()
        self.current_rect = QRect()
        self.normalized_rect: Optional[Tuple[float, float, float, float]] = None
        self.pixmap_image_size = (1600, 900)
        self._pixmap_orig: Optional[QPixmap] = None

    def set_pil_image(self, img: Image.Image, initial_norm: Optional[Tuple[float, float, float, float]] = None):
        self.pixmap_image_size = img.size
        img_rgb = img.convert("RGBA")
        data = img_rgb.tobytes("raw", "RGBA")
        qim = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        self._pixmap_orig = QPixmap.fromImage(qim)
        self._update_scaled_pixmap()

        if initial_norm:
            self._set_normalized_rect(*initial_norm)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()
        if self.normalized_rect:
            self._apply_normalized_to_rubberband(*self.normalized_rect)

    def _update_scaled_pixmap(self):
        if self._pixmap_orig:
            scaled = self._pixmap_orig.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)

    def _get_display_rect(self) -> QRect:
        if not self.pixmap() or self.pixmap().isNull():
            return self.rect()
        pm_size = self.pixmap().size()
        x = (self.width() - pm_size.width()) // 2
        y = (self.height() - pm_size.height()) // 2
        return QRect(x, y, pm_size.width(), pm_size.height())

    def _set_normalized_rect(self, nx: float, ny: float, nw: float, nh: float):
        self.normalized_rect = (nx, ny, nw, nh)
        self._apply_normalized_to_rubberband(nx, ny, nw, nh)

    def _apply_normalized_to_rubberband(self, nx: float, ny: float, nw: float, nh: float):
        disp = self._get_display_rect()
        rx = disp.x() + int(nx * disp.width())
        ry = disp.y() + int(ny * disp.height())
        rw = int(nw * disp.width())
        rh = int(nh * disp.height())
        self.current_rect = QRect(rx, ry, rw, rh)
        if not self.rubber_band:
            self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.rubber_band.setGeometry(self.current_rect)
        self.rubber_band.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            if not self.rubber_band:
                self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if self.rubber_band and self.rubber_band.isVisible() and event.buttons() & Qt.MouseButton.LeftButton:
            curr = event.position().toPoint()
            disp = self._get_display_rect()
            clamped_x = max(disp.left(), min(disp.right(), curr.x()))
            clamped_y = max(disp.top(), min(disp.bottom(), curr.y()))
            self.current_rect = QRect(self.origin, QPoint(clamped_x, clamped_y)).normalized()
            self.rubber_band.setGeometry(self.current_rect)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rubber_band:
            disp = self._get_display_rect()
            if disp.width() > 0 and disp.height() > 0 and self.current_rect.width() > 10 and self.current_rect.height() > 10:
                nx = max(0.0, min(1.0, (self.current_rect.left() - disp.left()) / disp.width()))
                ny = max(0.0, min(1.0, (self.current_rect.top() - disp.top()) / disp.height()))
                nw = max(0.01, min(1.0 - nx, self.current_rect.width() / disp.width()))
                nh = max(0.01, min(1.0 - ny, self.current_rect.height() / disp.height()))
                self.crop_changed.emit(nx, ny, nw, nh)

    def get_normalized_crop(self) -> Optional[Tuple[float, float, float, float]]:
        disp = self._get_display_rect()
        if not self.current_rect.isValid() or self.current_rect.width() < 10 or self.current_rect.height() < 10:
            return None
        nx = max(0.0, min(1.0, (self.current_rect.left() - disp.left()) / disp.width()))
        ny = max(0.0, min(1.0, (self.current_rect.top() - disp.top()) / disp.height()))
        nw = max(0.01, min(1.0 - nx, self.current_rect.width() / disp.width()))
        nh = max(0.01, min(1.0 - ny, self.current_rect.height() / disp.height()))
        return nx, ny, nw, nh


class PresetCropVisualEditor(QDialog):
    """
    Visual crop editor dialog:
    - Captures a live frame from the emulator
    - Lets the user drag a selection box
    - Displays exact percentage coordinates (cropX, cropY, cropW, cropH)
    - Saves crop boundaries into emulator configuration
    """
    def __init__(self, serial: str, service: EmulatorService, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.service = service
        self.setWindowTitle(f"Preset Crop Visual Editor - {serial}")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicon.ico"))
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(840, 560)
        self.resize(980, 660)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet(VSCODE_THEME)

        self.cfg = get_node_config(self.serial)
        self._init_ui()
        self._load_live_frame()

    def _init_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(20, 18, 20, 18)
        vbox.setSpacing(14)

        top_row = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)

        alias = self.cfg.get("customName", "").strip()
        header_text = f"Crop Calibrator - {alias} ({self.serial})" if alias else f"Crop Calibrator - {self.serial}"
        mode = self.cfg.get("mode", "BR")
        preset_id = self.cfg.get("preset", "")
        
        all_presets = PresetService.load_presets()
        preset_name = all_presets.get(preset_id, {}).get("name", preset_id) if preset_id else "Default"

        title_lbl = QLabel(header_text)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f0f6fc;")
        v_title.addWidget(title_lbl)

        preset_info_lbl = QLabel(f"Mode: {mode}  |  Active Preset: {preset_name}")
        preset_info_lbl.setStyleSheet("font-size: 12px; color: #38bdf8; font-weight: 600;")
        v_title.addWidget(preset_info_lbl)

        top_row.addLayout(v_title)
        top_row.addStretch()

        self.refresh_btn = QPushButton("Recapture Frame")
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #38bdf8;
                border: 1px solid #30363d;
                padding: 6px 14px;
                font-weight: 600;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)
        self.refresh_btn.clicked.connect(self._load_live_frame)
        top_row.addWidget(self.refresh_btn)
        vbox.addLayout(top_row)

        desc_lbl = QLabel(
            "Click and drag on the live emulator frame below to calibrate the scoreboard crop area.\n"
            "This region will be extracted and dispatched to your Discord Webhook."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.4;")
        vbox.addWidget(desc_lbl)

        # Interactive Canvas
        self.canvas = InteractiveCropCanvas()
        self.canvas.crop_changed.connect(self._on_crop_changed)
        vbox.addWidget(self.canvas, 1)

        # Bottom Bar with Coordinate Display and Buttons
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("background-color: #161b22; border: 1px solid #262c36; border-radius: 6px;")
        b_layout = QHBoxLayout(bottom_frame)
        b_layout.setContentsMargins(14, 10, 14, 10)
        b_layout.setSpacing(10)

        self.coords_lbl = QLabel("Crop: Full Frame (No crop)")
        self.coords_lbl.setStyleSheet("color: #a5f3fc; font-family: monospace; font-size: 13px; font-weight: 600;")
        b_layout.addWidget(self.coords_lbl)

        b_layout.addStretch()

        reset_btn = QPushButton("Reset Full Frame")
        reset_btn.setFixedHeight(34)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                padding: 6px 14px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
        """)
        reset_btn.clicked.connect(self._reset_crop)
        b_layout.addWidget(reset_btn)

        save_btn = QPushButton("Apply & Save Crop")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self._save_crop)
        b_layout.addWidget(save_btn)

        vbox.addWidget(bottom_frame)

    def _load_live_frame(self):
        frame = self.service.capture_frame(self.serial)
        if not frame:
            frame = Image.new("RGB", (1600, 900), color=(20, 24, 33))

        cx = self.cfg.get("cropX")
        cy = self.cfg.get("cropY")
        cw = self.cfg.get("cropW")
        ch = self.cfg.get("cropH")

        if cx is None or cy is None or cw is None or ch is None:
            preset_id = self.cfg.get("preset")
            all_presets = PresetService.load_presets()
            p = all_presets.get(preset_id, {})
            cx = p.get("cropX")
            cy = p.get("cropY")
            cw = p.get("cropW")
            ch = p.get("cropH")

        init_norm = None
        if cx is not None and cy is not None and cw is not None and ch is not None:
            init_norm = (float(cx), float(cy), float(cw), float(ch))
            self._update_coords_display(init_norm[0], init_norm[1], init_norm[2], init_norm[3])
        else:
            self.coords_lbl.setText("Crop: Full Frame (No crop)")

        self.canvas.set_pil_image(frame, init_norm)

    def _on_crop_changed(self, nx: float, ny: float, nw: float, nh: float):
        self._update_coords_display(nx, ny, nw, nh)

    def _update_coords_display(self, nx: float, ny: float, nw: float, nh: float):
        self.coords_lbl.setText(f"X: {nx*100:.1f}%  Y: {ny*100:.1f}%  W: {nw*100:.1f}%  H: {nh*100:.1f}%")

    def _reset_crop(self):
        if self.canvas.rubber_band:
            self.canvas.rubber_band.hide()
        self.canvas.current_rect = QRect()
        self.coords_lbl.setText("Crop: Full Frame (No crop)")

    def _save_crop(self):
        norm = self.canvas.get_normalized_crop()
        if norm is None:
            self.cfg["cropX"] = None
            self.cfg["cropY"] = None
            self.cfg["cropW"] = None
            self.cfg["cropH"] = None
        else:
            nx, ny, nw, nh = norm
            self.cfg["cropX"] = round(nx, 4)
            self.cfg["cropY"] = round(ny, 4)
            self.cfg["cropW"] = round(nw, 4)
            self.cfg["cropH"] = round(nh, 4)

        save_node_config(self.serial, self.cfg)
        QMessageBox.information(self, "Crop Saved", f"Preset crop boundaries applied to {self.serial}!")
        self.accept()
