"""ChannelBadge widget displays a spectrum channel label with its color."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from colorlab_pro.ui.resources.theme import channel_color


class ChannelBadge(QLabel):
    """A small colored badge showing a channel label such as R, G, B."""

    def __init__(self, channel: str, parent: QWidget | None = None) -> None:
        """Initialize the badge.

        Args:
            channel: Channel label (e.g. "R", "G", "B", "IR").
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._channel = channel.upper()
        self.setText(self._channel)
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply a rounded badge style using the channel color."""
        color = channel_color(self._channel)
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 8px;
                padding: 2px 6px;
                font-weight: bold;
                font-size: 10px;
            }}
            """
        )

    @property
    def channel(self) -> str:
        """Return the channel label."""
        return self._channel
