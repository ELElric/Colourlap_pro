"""Unit tests for colorlab_pro.engines.white_point_calculator (T-06)."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines import white_point_calculator as wpc

# ---- fixtures ----


@pytest.fixture
def rgb_primaries(standard_wavelengths: np.ndarray) -> list[Spectrum]:
    """Simple RGB LED primaries."""
    r = np.exp(-0.5 * ((standard_wavelengths - 630.0) / 8.5) ** 2)
    g = np.exp(-0.5 * ((standard_wavelengths - 530.0) / 12.7) ** 2)
    b = np.exp(-0.5 * ((standard_wavelengths - 450.0) / 8.5) ** 2)
    return [
        Spectrum(wavelengths=standard_wavelengths, values=r, unit="a.u."),
        Spectrum(wavelengths=standard_wavelengths, values=g, unit="a.u."),
        Spectrum(wavelengths=standard_wavelengths, values=b, unit="a.u."),
    ]


# ---- mixing_weights ----


class TestMixingWeights:
    def test_weights_sum_to_one(self, rgb_primaries: list[Spectrum]) -> None:
        w, achieved = wpc.mixing_weights(rgb_primaries, XY(0.3127, 0.3290))
        assert len(w) == 3
        assert pytest.approx(1.0) == float(np.sum(w))
        assert np.all(w >= 0)

    def test_achieved_close_to_target(self, rgb_primaries: list[Spectrum]) -> None:
        target = XY(0.3127, 0.3290)
        _, achieved = wpc.mixing_weights(rgb_primaries, target)
        err = float(np.hypot(achieved.x - target.x, achieved.y - target.y))
        assert err < 0.02

    def test_delta_xy_helper(self, rgb_primaries: list[Spectrum]) -> None:
        err = wpc.delta_xy_to_target(rgb_primaries, XY(0.3127, 0.3290))
        assert err < 0.02

    def test_not_enough_primaries_raises(self) -> None:
        with pytest.raises(ValueError, match="at least two primaries"):
            wpc.mixing_weights([], XY(0.3, 0.3))

    def test_achieved_xy_returned(self, rgb_primaries: list[Spectrum]) -> None:
        _, achieved = wpc.mixing_weights(rgb_primaries, XY(0.33, 0.33))
        assert isinstance(achieved, XY)
        assert 0.0 <= achieved.x <= 1.0
        assert 0.0 <= achieved.y <= 1.0


# ---- nearest_white_point ----


class TestNearestWhitePoint:
    def test_d65_recognized(self) -> None:
        name, dist = wpc.nearest_white_point(XY(0.3127, 0.3290))
        assert name == "D65"
        assert dist == pytest.approx(0.0, abs=1e-6)

    def test_e_recognized(self) -> None:
        name, dist = wpc.nearest_white_point(XY(1.0 / 3.0, 1.0 / 3.0))
        assert name == "E"
        assert dist < 0.05

    def test_returns_tuple(self) -> None:
        result = wpc.nearest_white_point(XY(0.3, 0.3))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], float)
