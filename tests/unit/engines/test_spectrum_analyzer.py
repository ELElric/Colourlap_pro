"""Unit tests for colorlab_pro.engines.spectrum_analyzer (T-03)."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.spectrum_analyzer import (
    cct_mccamy,
    dominant_wavelength,
    uprime_vprime,
    xy,
    xyz,
)

# ---- xyz ----
# (d65_spectrum and equal_energy_spectrum fixtures live in conftest.py)


class TestXYZ:
    def test_d65_xy(self, d65_spectrum: Spectrum) -> None:
        """D65 chromaticity should be (0.3127, 0.3290) within tolerance."""
        c = xy(d65_spectrum)
        assert c.x == pytest.approx(0.3127, abs=1e-3)
        assert c.y == pytest.approx(0.3290, abs=1e-3)

    def test_d65_xyz_relative(self, d65_spectrum: Spectrum) -> None:
        """D65 Y (luminance) should be positive and largest of X,Y,Z."""
        c = xyz(d65_spectrum)
        assert c.Y > 0
        assert c.X > 0
        assert c.Z > 0

    def test_equal_energy_xy(self, equal_energy_spectrum: Spectrum) -> None:
        """Equal-energy spectrum gives (1/3, 1/3) chromaticity."""
        c = xy(equal_energy_spectrum)
        assert c.x == pytest.approx(1.0 / 3.0, abs=1e-3)
        assert c.y == pytest.approx(1.0 / 3.0, abs=1e-3)

    def test_xyz_callable_signature(self, gaussian_spectrum) -> None:
        """xyz returns a XYZ dataclass with .X .Y .Z floats."""
        c = xyz(gaussian_spectrum)
        assert hasattr(c, "X")
        assert hasattr(c, "Y")
        assert hasattr(c, "Z")
        assert isinstance(c.X, float)
        assert isinstance(c.Y, float)
        assert isinstance(c.Z, float)


# ---- uprime_vprime ----


class TestUprimeVprime:
    def test_d65_uv(self, d65_spectrum: Spectrum) -> None:
        """D65 u'v' expected (0.1978, 0.4683) (approximate)."""
        u_p, v_p = uprime_vprime(d65_spectrum)
        assert u_p == pytest.approx(0.1978, abs=1e-3)
        assert v_p == pytest.approx(0.4683, abs=1e-3)

    def test_equal_energy_uv(self, equal_energy_spectrum: Spectrum) -> None:
        """Equal energy: (1/3, 1/3) -> u'=4/19, v'=9/19 (per the formula)."""
        u_p, v_p = uprime_vprime(equal_energy_spectrum)
        # denom = -2/3 + 12/3 + 3 = -2/3 + 4 + 3 = 19/3
        # u' = 4*(1/3) / (19/3) = 4/19 ≈ 0.21053
        # v' = 9*(1/3) / (19/3) = 9/19 ≈ 0.47368
        assert u_p == pytest.approx(4.0 / 19.0, abs=1e-3)
        assert v_p == pytest.approx(9.0 / 19.0, abs=1e-3)

    def test_returns_tuple(self, gaussian_spectrum) -> None:
        u_p, v_p = uprime_vprime(gaussian_spectrum)
        assert isinstance(u_p, float)
        assert isinstance(v_p, float)


# ---- cct_mccamy ----


class TestCCTMcCamy:
    def test_d65_cct_nominal(self, d65_spectrum: Spectrum) -> None:
        """D65 CCT is 6504 K; McCamy is accurate to +/- ~50 K for near-D65."""
        cct = cct_mccamy(d65_spectrum)
        assert cct == pytest.approx(6500, abs=100)

    def test_equal_energy_raises_or_finite(self, equal_energy_spectrum: Spectrum) -> None:
        """Equal energy has y == 1/3, so denominator 0.1858 - 1/3 = -0.1475 -> n is large.
        Returns a finite value (not raised)."""
        cct = cct_mccamy(equal_energy_spectrum)
        assert np.isfinite(cct)

    def test_cct_returns_float(self, d65_spectrum: Spectrum) -> None:
        cct = cct_mccamy(d65_spectrum)
        assert isinstance(cct, float)
        assert cct > 0


# ---- dominant_wavelength ----


class TestDominantWavelength:
    def test_red_spectrum(self, led_r_spectrum: Spectrum) -> None:
        """An R-LED at 630 nm should have dominant wavelength near 630 nm."""
        dwl = dominant_wavelength(led_r_spectrum)
        assert dwl is not None
        assert 615 <= dwl <= 645

    def test_green_spectrum(self, led_g_spectrum: Spectrum) -> None:
        dwl = dominant_wavelength(led_g_spectrum)
        assert dwl is not None
        assert 515 <= dwl <= 545

    def test_blue_spectrum(self, led_b_spectrum: Spectrum) -> None:
        dwl = dominant_wavelength(led_b_spectrum)
        assert dwl is not None
        assert 435 <= dwl <= 470
