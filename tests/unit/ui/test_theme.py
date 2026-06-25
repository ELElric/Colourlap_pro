"""Unit tests for the theme module."""
from __future__ import annotations

from colorlab_pro.ui.resources.theme import CHANNEL_COLORS, channel_color


def test_channel_color_known():
    assert channel_color("R") == CHANNEL_COLORS["R"]
    assert channel_color("g") == CHANNEL_COLORS["G"]


def test_channel_color_unknown_defaults():
    assert channel_color("X") == "#6B7280"
