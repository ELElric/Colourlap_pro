"""Application-wide theme and stylesheet resources."""

from __future__ import annotations

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
