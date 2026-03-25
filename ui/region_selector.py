"""Screen region selector - screenshot-based overlay.

Takes a full screenshot, shows it as the overlay background,
so the user can see exactly where to select the capture region.
"""

import logging
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtCore import QEventLoop, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

logger = logging.getLogger(__name__)


class RegionSelector(QWidget):
    """Full-screen overlay with screenshot background for region selection."""

    region_selected = pyqtSignal(dict)
    selection_cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._start_pos: QPoint | None = None
        self._current_pos: QPoint | None = None
        self._is_selecting = False
        self._loop: QEventLoop | None = None
        self._bg_pixmap: QPixmap | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def start(self):
        """Capture full screen, then show as background for selection."""
        # 1. Take a full-screen screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            subprocess.run(
                ["screencapture", "-x", tmp_path],
                capture_output=True,
                timeout=5,
            )
            if not Path(tmp_path).exists():
                self.selection_cancelled.emit()
                return

            self._bg_pixmap = QPixmap(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if self._bg_pixmap is None or self._bg_pixmap.isNull():
            self.selection_cancelled.emit()
            return

        # 2. Fullscreen with the screenshot as background
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)
            self._screen_ratio = screen.devicePixelRatio()
        else:
            self._screen_ratio = 1.0

        # 3. Show and block with local event loop
        self._loop = QEventLoop()
        self.showFullScreen()
        self._loop.exec()

    def _finish(self):
        self.close()
        if self._loop:
            self._loop.quit()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw screenshot as background
        if self._bg_pixmap:
            painter.drawPixmap(self.rect(), self._bg_pixmap)

        # Dim the whole screen slightly
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        # Draw instruction text
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            self.rect().center().x() - 150,
            30,
            "拖曳框選遊戲狀態列區域（ESC 取消）"
        )

        if self._start_pos and self._current_pos and self._is_selecting:
            rect = QRect(self._start_pos, self._current_pos).normalized()

            # Clear the dim for selected area — show original screenshot
            if self._bg_pixmap:
                # Map widget coords to pixmap coords
                ratio = self._screen_ratio
                src_rect = QRect(
                    int(rect.x() * ratio),
                    int(rect.y() * ratio),
                    int(rect.width() * ratio),
                    int(rect.height() * ratio),
                )
                painter.drawPixmap(rect, self._bg_pixmap, src_rect)

            # Gold border
            pen = QPen(QColor(240, 192, 64), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Size label
            w = rect.width()
            h = rect.height()
            painter.setPen(QColor(240, 192, 64))
            painter.drawText(rect.x() + 4, rect.y() - 8, f"{w} x {h}")

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.pos()
            self._current_pos = event.pos()
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            if self._start_pos and self._current_pos:
                rect = QRect(self._start_pos, self._current_pos).normalized()
                if rect.width() > 10 and rect.height() > 10:
                    # Convert to actual screen pixel coordinates (Retina)
                    ratio = self._screen_ratio
                    region = {
                        "x": int(rect.x() * ratio),
                        "y": int(rect.y() * ratio),
                        "w": int(rect.width() * ratio),
                        "h": int(rect.height() * ratio),
                    }
                    logger.info("Region selected: %s (ratio=%.1f)", region, ratio)
                    self._finish()
                    self.region_selected.emit(region)
                    return

            self._finish()
            self.selection_cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._is_selecting = False
            self._finish()
            self.selection_cancelled.emit()
