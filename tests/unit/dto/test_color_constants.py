"""Tests for dto.color_constants module."""

from __future__ import annotations

from colorlab_pro.dto.color_constants import (
    DELTA_E_METHODS,
    ILLUMINANT_CHOICES,
    OBSERVER_CHOICES,
)


def test_delta_e_methods():
    assert isinstance(DELTA_E_METHODS, list)
    assert "CIE 2000" in DELTA_E_METHODS
    assert "CIE 1976" in DELTA_E_METHODS


def test_observer_choices():
    assert isinstance(OBSERVER_CHOICES, list)
    assert "CIE 1931 2 Degree Standard Observer" in OBSERVER_CHOICES


def test_illuminant_choices():
    assert isinstance(ILLUMINANT_CHOICES, list)
    assert "D65" in ILLUMINANT_CHOICES
    assert "E" in ILLUMINANT_CHOICES
