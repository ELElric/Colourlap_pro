"""Tests for dto.channels module."""

from __future__ import annotations

from colorlab_pro.dto.channels import (
    ALL_CATEGORIES,
    CATEGORY_CF,
    CATEGORY_LED,
    CATEGORY_OPTIONS,
    CATEGORY_QD,
    CATEGORY_WHITE,
    CHANNEL_B,
    CHANNEL_G,
    CHANNEL_OPTIONS,
    CHANNEL_R,
)


def test_channel_constants():
    assert CHANNEL_R == "R"
    assert CHANNEL_G == "G"
    assert CHANNEL_B == "B"


def test_category_constants():
    assert CATEGORY_LED == "LED"
    assert CATEGORY_CF == "CF"
    assert CATEGORY_QD == "QD"
    assert CATEGORY_WHITE == "白光"
    assert ALL_CATEGORIES == [CATEGORY_LED, CATEGORY_CF, CATEGORY_QD, CATEGORY_WHITE]


def test_channel_options_format():
    assert isinstance(CHANNEL_OPTIONS, list)
    assert len(CHANNEL_OPTIONS) == 4  # Auto-detect + R + G + B
    labels = [label for label, _ in CHANNEL_OPTIONS]
    assert "Auto-detect" in labels
    assert "R" in labels
    assert "G" in labels
    assert "B" in labels


def test_category_options_format():
    assert isinstance(CATEGORY_OPTIONS, list)
    assert len(CATEGORY_OPTIONS) == 5  # Auto-detect + LED + CF + QD + 白光
