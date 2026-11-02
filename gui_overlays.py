#!/usr/bin/env python3
"""gwperintahin — Screen Overlay Widgets (Color Picker, Region Capture, Record Mode)"""

from PIL import Image
from PIL.ImageQt import ImageQt

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout,
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, pyqtSlot, QRectF,
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPixmap, QFont,
)

from PIL import ImageGrab


# ═════════════════════════════════════════════════════════════════════════
#  Color Picker Overlay
# ═════════════════════════════════════════════════════════════════════════

class ColorPickerOverlay(QWidget):
    """Fullscreen transparent overlay to pick a colour from any pixel."""

    color_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Pre-capture screenshot to sample from (avoids reading ourselves)
        self._screen_capture = ImageGrab.grab()

        # Info label
        self._info = QLabel(self)
        self._info.setStyleSheet("""
            QLabel {
                background: rgba(20, 20, 20, 220);
                color: #fff;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 8px 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
        """)
        self._info.setFixedSize(260, 100)
        self._info.hide()

        # Magnifier preview
        self._magnifier_size = 120
        self._magnifier_zoom = 6
        self._magnifier_label = QLabel(self)
        self._magnifier_label.setFixedSize(self._magnifier_size, self._magnifier_size)
        self._magnifier_label.setStyleSheet("""
            QLabel {
                border: 2px solid white;
                border-radius: 4px;
            }
        """)
        self._magnifier_label.hide()

        self.showFullScreen()
        self.raise_()

        # Instructions
        self._help = QLabel("Click anywhere to pick colour · Press ESC to cancel", self)
        self._help.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 180);
                color: #ccc;
                border: none;
                font-size: 14px;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        self._help.adjustSize()
        self._help.move(
            (self.width() - self._help.width()) // 2,
            self.height() - 60
        )
        self._help.show()

        self._current_color = "#000000"

    def _update_info(self, x, y):
        w, h = self._screen_capture.size
        if 0 <= x < w and 0 <= y < h:
            rgb = self._screen_capture.getpixel((x, y))
            hex_color = "#{:02X}{:02X}{:02X}".format(*rgb[:3])
            self._current_color = hex_color

            # Magnifier
            left = max(0, x - self._magnifier_zoom // 2)
            top = max(0, y - self._magnifier_zoom // 2)
            right = min(w, left + self._magnifier_zoom)
            bottom = min(h, top + self._magnifier_zoom)
            region = self._screen_capture.crop((left, top, right, bottom))
            region = region.resize(
                (self._magnifier_size, self._magnifier_size),
                Image.NEAREST
            )

            qimg = ImageQt(region)
            pix = QPixmap.fromImage(qimg)
            self._magnifier_label.setPixmap(pix)
            self._magnifier_label.show()

            # Info text
            text = (
                f"<b style='color:{hex_color};font-size:18px;'>&#11044;</b>  "
                f"<span style='font-size:16px;'>{hex_color}</span><br>"
                f"<span style='color:#999;'>RGB: {rgb[0]}, {rgb[1]}, {rgb[2]}</span><br>"
                f"<span style='color:#999;'>X: {x}  Y: {y}</span>"
            )
            self._info.setText(text)
            self._info.adjustSize()

            # Position info box near cursor but within screen bounds
            ix = x + 20
            iy = y + 20
            if ix + self._info.width() > self.width():
                ix = x - self._info.width() - 10
            if iy + self._info.height() > self.height():
                iy = y - self._info.height() - 10
            self._info.move(ix, iy)
            self._info.show()

            # Position magnifier
            mx = x - self._magnifier_size // 2
            my = y - self._magnifier_size - 60
            if my < 0:
                my = y + 30
            self._magnifier_label.move(mx, my)

    def mouseMoveEvent(self, event):
        self._update_info(int(event.position().x()), int(event.position().y()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.color_selected.emit(self._current_color)
            self.close()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


# ═════════════════════════════════════════════════════════════════════════
#  Region Capture Overlay
# ═════════════════════════════════════════════════════════════════════════

class RegionCaptureOverlay(QWidget):
    """Fullscreen overlay to drag-select a screen region."""

    region_captured = pyqtSignal(tuple)  # (x, y, w, h)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_pos = None
        self._end_pos = None
        self._dragging = False

        self.showFullScreen()
        self.raise_()

        # Instructions
        self._help = QLabel("Drag to select region · ESC to cancel", self)
        self._help.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 180);
                color: #ccc;
                border: none;
                font-size: 14px;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        self._help.adjustSize()
        self._help.move(
            (self.width() - self._help.width()) // 2,
            self.height() - 60
        )
        self._help.show()

        self._dim_color = QColor(0, 0, 0, 120)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim the entire screen
        painter.fillRect(self.rect(), self._dim_color)

        if self._start_pos and self._end_pos:
            rect = QRectF(self._start_pos, self._end_pos).normalized()
            # Clear the selected region
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # Draw border
            pen = QPen(QColor("#00A8FF"), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw size label
            size_text = f"{int(rect.width())} \u00d7 {int(rect.height())}"
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Segoe UI", 12)
            painter.setFont(font)
            painter.drawText(
                QRectF(rect.x(), rect.y() - 28, rect.width(), 24),
                Qt.AlignmentFlag.AlignCenter,
                size_text
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.position()
            self._end_pos = event.position()
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._end_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            x1 = min(self._start_pos.x(), self._end_pos.x())
            y1 = min(self._start_pos.y(), self._end_pos.y())
            x2 = max(self._start_pos.x(), self._end_pos.x())
            y2 = max(self._start_pos.y(), self._end_pos.y())
            w = x2 - x1
            h = y2 - y1
            if w > 5 and h > 5:
                self.region_captured.emit((int(x1), int(y1), int(w), int(h)))
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


# ═════════════════════════════════════════════════════════════════════════
#  Record Mode Overlay
# ═════════════════════════════════════════════════════════════════════════

class RecordModeOverlay(QWidget):
    """
    Floating overlay shown while recording macro actions.
    Displays recording status, step count, and a stop button.
    """

    stop_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(260, 60)

        self._bg_color = QColor(20, 22, 28, 230)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

        # Recording indicator (animated red dot placeholder)
        self._indicator = QLabel("\u25cf")
        self._indicator.setStyleSheet("""
            QLabel {
                font-size: 20px;
                color: #ff4444;
            }
        """)
        layout.addWidget(self._indicator)

        # Status label
        self._status_label = QLabel("Recording\u2026")
        self._status_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        layout.addWidget(self._status_label)

        # Step count
        self._step_label = QLabel("0 steps")
        self._step_label.setStyleSheet("""
            QLabel {
                color: #9a9b9e;
                font-size: 12px;
            }
        """)
        layout.addWidget(self._step_label)

        layout.addStretch()

        # Stop button
        stop_btn = QPushButton("\u23f9 Stop [F6]")
        stop_btn.setStyleSheet("""
            QPushButton {
                background: #cc3333;
                color: #fff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #ee4444;
            }
        """)
        stop_btn.clicked.connect(self.stop_requested.emit)
        layout.addWidget(stop_btn)

        # Position in top-center of screen
        screen = QApplication.primaryScreen().size()
        self.move(
            (screen.width() - self.width()) // 2,
            20
        )

        # Blinking timer for indicator
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(600)
        self._blink_visible = True

        # Make it draggable
        self._drag_pos = None

    def _blink(self):
        self._blink_visible = not self._blink_visible
        self._indicator.setVisible(self._blink_visible)

    @pyqtSlot(int)
    def update_step_count(self, count: int):
        self._step_label.setText(f"{count} step{'s' if count != 1 else ''}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(QColor(60, 70, 90, 200), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
