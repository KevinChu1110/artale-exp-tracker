"""iOS-style toggle switch widget for PyQt6."""

from PyQt6.QtCore import QPropertyAnimation, QRectF, Qt, pyqtProperty, pyqtSignal, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """A toggle switch widget styled like iOS/macOS."""

    toggled = pyqtSignal(bool)

    def __init__(self, text: str = "", checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._text = text
        self._knob_x = 22.0 if checked else 2.0
        self._animation = QPropertyAnimation(self, b"knob_x")
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.setFixedHeight(26)
        self.setMinimumWidth(44 + len(text) * 14 + 12)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @pyqtProperty(float)
    def knob_x(self):
        return self._knob_x

    @knob_x.setter
    def knob_x(self, val):
        self._knob_x = val
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        self._checked = checked
        self._knob_x = 22.0 if checked else 2.0
        self.update()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._animation.setStartValue(self._knob_x)
        self._animation.setEndValue(22.0 if self._checked else 2.0)
        self._animation.start()
        self.toggled.emit(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track
        track_w, track_h = 44, 24
        track_rect = QRectF(0, 1, track_w, track_h)
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, track_h / 2, track_h / 2)

        if self._checked:
            p.fillPath(track_path, QColor(76, 217, 100))  # green
        else:
            p.fillPath(track_path, QColor(120, 120, 128))  # gray

        # Knob
        knob_size = 20
        knob_rect = QRectF(self._knob_x, 3, knob_size, knob_size)
        knob_path = QPainterPath()
        knob_path.addEllipse(knob_rect)
        p.fillPath(knob_path, QColor(255, 255, 255))

        # Text label
        if self._text:
            p.setPen(QColor(224, 224, 224))
            p.drawText(track_w + 8, 17, self._text)

        p.end()

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        text_width = len(self._text) * 14 + 12 if self._text else 0
        return QSize(44 + text_width, 26)
