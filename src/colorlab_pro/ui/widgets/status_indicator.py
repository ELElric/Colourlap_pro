"""StatusIndicator widget shows a colored status dot with a label."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class StatusIndicator(QWidget):
    """A colored dot next to a text label indicating status."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Initialize the indicator.

        Args:
            text: Label text.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._color = QColor("#6B7280")
        self._text = text
        self._label = QLabel(text, self)
        self._dot_size = 10

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._label)
        self.setLayout(layout)

        self.setMinimumSize(self._dot_size + 4, self._dot_size + 4)

    def set_status(self, color: str, text: str | None = None) -> None:
        """Update the indicator color and optional label text."""
        self._color = QColor(color)
        if text is not None:
            self._text = text
            self._label.setText(text)
        self.update()

    @property
    def color(self) -> QColor:
        """Return the current indicator color."""
        return self._color

    @property
    def label(self) -> str:
        """Return the current label text."""
        return self._text

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw the colored dot at the left of the widget."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        margin = 2
        painter.drawEllipse(
            margin,
            (self.height() - self._dot_size) // 2,
            self._dot_size,
            self._dot_size,
        )
        painter.end()
