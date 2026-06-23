"""Tests for dto.color module."""

from __future__ import annotations

import pytest

from colorlab_pro.dto.color import XY, XYZ, Gamut


class TestXY:
    def test_creation(self):
        xy = XY(x=0.3127, y=0.3290)
        assert xy.x == 0.3127
        assert xy.y == 0.3290

    def test_immutable(self):
        xy = XY(x=0.3127, y=0.3290)
        with pytest.raises(AttributeError):
            xy.x = 0.5


class TestXYZ:
    def test_creation(self):
        xyz = XYZ(X=0.9505, Y=1.0000, Z=1.0890)
        assert xyz.X == 0.9505
        assert xyz.Y == 1.0000
        assert xyz.Z == 1.0890


class TestGamut:
    def test_creation(self):
        gamut = Gamut(
            name="sRGB",
            red=(0.64, 0.33),
            green=(0.30, 0.60),
            blue=(0.15, 0.06),
            white=(0.3127, 0.3290),
        )
        assert gamut.name == "sRGB"
        assert gamut.red == (0.64, 0.33)

    def test_immutable(self):
        gamut = Gamut(
            name="sRGB",
            red=(0.64, 0.33),
            green=(0.30, 0.60),
            blue=(0.15, 0.06),
            white=(0.3127, 0.3290),
        )
        with pytest.raises(AttributeError):
            gamut.name = "DCI-P3"
