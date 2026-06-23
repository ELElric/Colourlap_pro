"""Application-wide theme and stylesheet resources."""

from __future__ import annotations

from enum import Enum


class ThemeName(str, Enum):
    """Supported application themes."""

    LIGHT = "light"
    DARK = "dark"


# Base color palette shared between themes.
PRIMARY = "#2563EB"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#EF4444"

# Channel-specific colors used in badges and plots.
CHANNEL_COLORS: dict[str, str] = {
    "R": "#EF4444",
    "G": "#10B981",
    "B": "#3B82F6",
    "W": "#6B7280",
    "C": "#06B6D4",
    "M": "#EC4899",
    "Y": "#EAB308",
    "IR": "#7C3AED",
}


def channel_color(channel: str) -> str:
    """Return the hex color for a channel label."""
    return CHANNEL_COLORS.get(channel.upper(), "#6B7280")


def stylesheet(theme: ThemeName = ThemeName.LIGHT) -> str:
    """Return the application QSS for the requested theme."""
    if theme == ThemeName.DARK:
        return _DARK_STYLESHEET
    return _LIGHT_STYLESHEET


_LIGHT_STYLESHEET = """
QMainWindow {
    background-color: #F3F4F6;
}

QMenuBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E5E7EB;
}

QMenuBar::item:selected {
    background-color: #E5E7EB;
}

QStatusBar {
    background-color: #FFFFFF;
    color: #374151;
    border-top: 1px solid #E5E7EB;
}

QLabel {
    color: #111827;
}

QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #1D4ED8;
}

QPushButton:disabled {
    background-color: #93C5FD;
}
"""

_DARK_STYLESHEET = """
QMainWindow {
    background-color: #111827;
}

QMenuBar {
    background-color: #1F2937;
    border-bottom: 1px solid #374151;
    color: #F9FAFB;
}

QMenuBar::item:selected {
    background-color: #374151;
}

QStatusBar {
    background-color: #1F2937;
    color: #D1D5DB;
    border-top: 1px solid #374151;
}

QLabel {
    color: #F9FAFB;
}

QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #1D4ED8;
}

QPushButton:disabled {
    background-color: #1E3A8A;
}
"""
