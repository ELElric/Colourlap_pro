"""Unit tests for the theme module."""

from __future__ import annotations

from colorlab_pro.ui.resources.theme import CHANNEL_COLORS, ThemeName, channel_color, stylesheet


def test_channel_color_known():
    assert channel_color("R") == CHANNEL_COLORS["R"]
    assert channel_color("g") == CHANNEL_COLORS["G"]


def test_channel_color_unknown_defaults():
    assert channel_color("X") == "#6B7280"


def test_stylesheet_light_contains_mainwindow():
    qss = stylesheet(ThemeName.LIGHT)
    assert "QMainWindow" in qss
    assert "#F3F4F6" in qss


def test_stylesheet_dark_contains_mainwindow():
    qss = stylesheet(ThemeName.DARK)
    assert "QMainWindow" in qss
    assert "#111827" in qss
