"""Unit tests for reusable UI widgets."""

from __future__ import annotations

from PySide6.QtGui import QColor

from colorlab_pro.ui.widgets.channel_badge import ChannelBadge
from colorlab_pro.ui.widgets.status_indicator import StatusIndicator


def test_channel_badge_text_and_channel(qtbot):
    badge = ChannelBadge("r")
    qtbot.addWidget(badge)
    assert badge.text() == "R"
    assert badge.channel == "R"


def test_channel_badge_style_contains_color(qtbot):
    badge = ChannelBadge("G")
    qtbot.addWidget(badge)
    assert "#10B981" in badge.styleSheet()


def test_status_indicator_defaults(qtbot):
    indicator = StatusIndicator("Idle")
    qtbot.addWidget(indicator)
    assert indicator.label == "Idle"
    assert indicator.color.name() == QColor("#6B7280").name()


def test_status_indicator_set_status(qtbot):
    indicator = StatusIndicator("Idle")
    qtbot.addWidget(indicator)
    indicator.set_status("#10B981", "Ready")
    assert indicator.label == "Ready"
    assert indicator.color.name() == QColor("#10B981").name()
