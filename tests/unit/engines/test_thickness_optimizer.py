"""Unit tests for colorlab_pro.engines.thickness_optimizer (T-06)."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines import thickness_optimizer as topt

# ---- fixtures ----


@pytest.fixture
def equal_source(standard_wavelengths: np.ndarray) -> Spectrum:
    """Flat white source spectrum before CF."""
    return Spectrum(
        wavelengths=standard_wavelengths,
        values=np.ones_like(standard_wavelengths),
        unit="a.u.",
    )


@pytest.fixture
def rgb_absorbers(standard_wavelengths: np.ndarray) -> list[Spectrum]:
    """Idealized R/G/B CF absorbers.

    Each absorber absorbs only outside its passband.
    """
    r_pass = (standard_wavelengths >= 580) & (standard_wavelengths <= 700)
    g_pass = (standard_wavelengths >= 480) & (standard_wavelengths <= 580)
    b_pass = (standard_wavelengths >= 380) & (standard_wavelengths <= 480)

    alpha_r = np.where(r_pass, 0.0, 2.0)
    alpha_g = np.where(g_pass, 0.0, 2.0)
    alpha_b = np.where(b_pass, 0.0, 2.0)

    return [
        Spectrum(wavelengths=standard_wavelengths, values=alpha_r, unit="1/um"),
        Spectrum(wavelengths=standard_wavelengths, values=alpha_g, unit="1/um"),
        Spectrum(wavelengths=standard_wavelengths, values=alpha_b, unit="1/um"),
    ]


# ---- optimize_thickness ----


class TestOptimizeThickness:
    def test_converges_and_bounds_respected(
        self,
        equal_source: Spectrum,
        rgb_absorbers: list[Spectrum],
    ) -> None:
        target = XY(0.3127, 0.3290)
        res = topt.optimize_thickness(target, equal_source, rgb_absorbers)
        assert res.converged
        assert len(res.thicknesses_um) == 3
        assert all(0.1 <= d <= 10.0 for d in res.thicknesses_um)
        assert res.delta_xy < 0.05

    def test_achieved_xy_matches_reported(
        self,
        equal_source: Spectrum,
        rgb_absorbers: list[Spectrum],
    ) -> None:
        target = XY(0.33, 0.33)
        res = topt.optimize_thickness(target, equal_source, rgb_absorbers)
        assert res.achieved_xy.x == pytest.approx(res.target_xy.x, abs=res.delta_xy + 1e-6)

    def test_result_fields(self, equal_source: Spectrum, rgb_absorbers: list[Spectrum]) -> None:
        res = topt.optimize_thickness(XY(0.3127, 0.3290), equal_source, rgb_absorbers)
        assert hasattr(res, "thicknesses_um")
        assert hasattr(res, "achieved_xy")
        assert hasattr(res, "target_xy")
        assert hasattr(res, "delta_xy")
        assert hasattr(res, "converged")
        assert hasattr(res, "iterations")

    def test_not_enough_absorbers_raises(self, equal_source: Spectrum) -> None:
        with pytest.raises(ValueError, match="at least two absorber channels"):
            topt.optimize_thickness(XY(0.3, 0.3), equal_source, [equal_source])


# ---- transmission_for_thicknesses ----


class TestTransmission:
    def test_returns_spectrum(
        self,
        equal_source: Spectrum,
        rgb_absorbers: list[Spectrum],
    ) -> None:
        out = topt.transmission_for_thicknesses(equal_source, rgb_absorbers, (1.0, 1.0, 1.0))
        assert isinstance(out, Spectrum)
        assert out.wavelengths.shape == equal_source.wavelengths.shape
        assert np.all(out.values >= 0)
        assert np.all(out.values <= equal_source.values + 1e-12)

    def test_zero_thickness_no_attenuation(
        self,
        equal_source: Spectrum,
        rgb_absorbers: list[Spectrum],
    ) -> None:
        out = topt.transmission_for_thicknesses(equal_source, rgb_absorbers, (0.0, 0.0, 0.0))
        np.testing.assert_allclose(out.values, equal_source.values, atol=1e-12)


# ---- optimize_thickness_display (display model) ----


@pytest.fixture
def rgb_sources(standard_wavelengths: np.ndarray) -> list[Spectrum]:
    """Idealized R/G/B emission source spectra."""
    r_pass = (standard_wavelengths >= 580) & (standard_wavelengths <= 700)
    g_pass = (standard_wavelengths >= 480) & (standard_wavelengths <= 580)
    b_pass = (standard_wavelengths >= 380) & (standard_wavelengths <= 480)

    return [
        Spectrum(wavelengths=standard_wavelengths, values=np.where(r_pass, 1.0, 0.01), unit="a.u."),
        Spectrum(wavelengths=standard_wavelengths, values=np.where(g_pass, 1.0, 0.01), unit="a.u."),
        Spectrum(wavelengths=standard_wavelengths, values=np.where(b_pass, 1.0, 0.01), unit="a.u."),
    ]


class TestOptimizeThicknessDisplay:
    def test_converges_and_returns_three_thicknesses(
        self,
        rgb_sources: list[Spectrum],
        rgb_absorbers: list[Spectrum],
    ) -> None:
        target = XY(0.3127, 0.3290)
        res = topt.optimize_thickness_display(target, rgb_sources, rgb_absorbers)
        assert res.converged
        assert len(res.thicknesses_um) == 3
        assert all(0.1 <= d <= 10.0 for d in res.thicknesses_um)

    def test_achieved_xy_close_to_target(
        self,
        rgb_sources: list[Spectrum],
        rgb_absorbers: list[Spectrum],
    ) -> None:
        target = XY(0.33, 0.33)
        res = topt.optimize_thickness_display(target, rgb_sources, rgb_absorbers)
        assert res.delta_xy < 0.1

    def test_per_channel_bounds_respected(
        self,
        rgb_sources: list[Spectrum],
        rgb_absorbers: list[Spectrum],
    ) -> None:
        target = XY(0.3127, 0.3290)
        bounds = [(0.5, 3.0), (0.2, 5.0), (0.1, 8.0)]
        res = topt.optimize_thickness_display(
            target, rgb_sources, rgb_absorbers, bounds_um=bounds
        )
        assert 0.5 <= res.thicknesses_um[0] <= 3.0
        assert 0.2 <= res.thicknesses_um[1] <= 5.0
        assert 0.1 <= res.thicknesses_um[2] <= 8.0

    def test_mismatched_source_absorber_raises(self, rgb_sources: list[Spectrum]) -> None:
        with pytest.raises(ValueError, match="must match"):
            topt.optimize_thickness_display(
                XY(0.3, 0.3), rgb_sources, [rgb_sources[0]]
            )

    def test_too_few_channels_raises(self, equal_source: Spectrum) -> None:
        with pytest.raises(ValueError, match="at least two"):
            topt.optimize_thickness_display(
                XY(0.3, 0.3), [equal_source], [equal_source]
            )

    def test_meta_contains_model_tag(
        self,
        rgb_sources: list[Spectrum],
        rgb_absorbers: list[Spectrum],
    ) -> None:
        res = topt.optimize_thickness_display(XY(0.3, 0.3), rgb_sources, rgb_absorbers)
        assert res.meta.get("model") == "display"


class TestDisplayTransmission:
    def test_returns_per_channel_spectra(
        self,
        rgb_sources: list[Spectrum],
        rgb_absorbers: list[Spectrum],
    ) -> None:
        out = topt.display_transmission_for_thicknesses(
            rgb_sources, rgb_absorbers, (1.0, 1.0, 1.0)
        )
        assert len(out) == 3
        for s in out:
            assert isinstance(s, Spectrum)
            assert np.all(s.values >= 0)

    def test_zero_thickness_returns_source(
        self,
        rgb_sources: list[Spectrum],
        rgb_absorbers: list[Spectrum],
    ) -> None:
        out = topt.display_transmission_for_thicknesses(
            rgb_sources, rgb_absorbers, (0.0, 0.0, 0.0)
        )
        for src, filtered in zip(rgb_sources, out, strict=True):
            np.testing.assert_allclose(filtered.values, src.values, atol=1e-12)
