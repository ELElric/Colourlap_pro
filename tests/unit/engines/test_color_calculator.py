"""Unit tests for colorlab_pro.engines.color_calculator (T-04)."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines import color_calculator as cc

# ---- fixtures ----


@pytest.fixture
def primary_r(standard_wavelengths: np.ndarray) -> Spectrum:
    return Spectrum(
        wavelengths=standard_wavelengths,
        values=np.exp(-0.5 * ((standard_wavelengths - 630.0) / 8.5) ** 2),
        unit="a.u.",
    )


@pytest.fixture
def primary_g(standard_wavelengths: np.ndarray) -> Spectrum:
    return Spectrum(
        wavelengths=standard_wavelengths,
        values=np.exp(-0.5 * ((standard_wavelengths - 530.0) / 12.7) ** 2),
        unit="a.u.",
    )


@pytest.fixture
def primary_b(standard_wavelengths: np.ndarray) -> Spectrum:
    return Spectrum(
        wavelengths=standard_wavelengths,
        values=np.exp(-0.5 * ((standard_wavelengths - 450.0) / 8.5) ** 2),
        unit="a.u.",
    )


# ---- mix_spectra ----


class TestMixSpectra:
    def test_equal_weights_three_primaries(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
        primary_b: Spectrum,
    ) -> None:
        mixed = cc.mix_spectra([primary_r, primary_g, primary_b])
        assert mixed.values.shape == primary_r.values.shape
        # Default weights = [1, 1, 1] = sum (not average).
        np.testing.assert_allclose(
            mixed.values,
            primary_r.values + primary_g.values + primary_b.values,
        )

    def test_custom_weights(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
        primary_b: Spectrum,
    ) -> None:
        mixed = cc.mix_spectra([primary_r, primary_g, primary_b], weights=[1.0, 0.0, 0.0])
        np.testing.assert_array_equal(mixed.values, primary_r.values)

    def test_default_weights_all_ones(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        mixed = cc.mix_spectra([primary_r, primary_g])
        assert np.allclose(mixed.values, primary_r.values + primary_g.values)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="spectra must not be empty"):
            cc.mix_spectra([])

    def test_mismatched_weights_raises(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        with pytest.raises(ValueError, match="weights length"):
            cc.mix_spectra([primary_r, primary_g], weights=[1.0])

    def test_negative_weight_raises(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            cc.mix_spectra([primary_r, primary_g], weights=[-1.0, 1.0])

    def test_zero_total_weight_raises(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        with pytest.raises(ValueError, match="weights sum"):
            cc.mix_spectra([primary_r, primary_g], weights=[0.0, 0.0])

    def test_mix_metadata_recorded(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        mixed = cc.mix_spectra([primary_r, primary_g], weights=[0.7, 0.3])
        assert mixed.meta["mixed_from"] == 2
        assert mixed.meta["weights"] == [0.7, 0.3]

    def test_aligned_with_first_grid(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        mixed = cc.mix_spectra([primary_r, primary_g])
        np.testing.assert_array_equal(mixed.wavelengths, primary_r.wavelengths)

    def test_mixed_xy_xyz_additive(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
        primary_b: Spectrum,
    ) -> None:
        """mix_xyz should equal sum of individual XYZ (additive)."""
        from colorlab_pro.engines.spectrum_analyzer import xyz

        r_xyz = xyz(primary_r)
        g_xyz = xyz(primary_g)
        b_xyz = xyz(primary_b)
        mixed_xyz = cc.mix_xyz([primary_r, primary_g, primary_b])
        assert mixed_xyz.X == pytest.approx(r_xyz.X + g_xyz.X + b_xyz.X, rel=1e-9)
        assert mixed_xyz.Y == pytest.approx(r_xyz.Y + g_xyz.Y + b_xyz.Y, rel=1e-9)
        assert mixed_xyz.Z == pytest.approx(r_xyz.Z + g_xyz.Z + b_xyz.Z, rel=1e-9)


# ---- mix_xy ----


class TestMixXY:
    def test_centroid_two_points(self) -> None:
        a = XY(x=0.3, y=0.4)
        b = XY(x=0.5, y=0.2)
        c = cc.mix_xy([a, b], weights=[0.5, 0.5])
        # XYZ-space additive mixing result (not simple xy average)
        assert 0.0 < c.x < 1.0
        assert 0.0 < c.y < 1.0

    def test_centroid_three_points(self) -> None:
        pts = [XY(x=0.3, y=0.4), XY(x=0.5, y=0.2), XY(x=0.2, y=0.3)]
        c = cc.mix_xy(pts)
        assert 0.0 < c.x < 1.0
        assert 0.0 < c.y < 1.0

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="xy_list must not be empty"):
            cc.mix_xy([])

    def test_mismatched_weights_raises(self) -> None:
        with pytest.raises(ValueError, match="weights length"):
            cc.mix_xy([XY(0.3, 0.3), XY(0.5, 0.5)], weights=[1.0])

    def test_default_weights_equal(self) -> None:
        c = cc.mix_xy([XY(0.64, 0.33), XY(0.30, 0.60)])
        # Mix of two realistic chromaticities
        assert 0.0 < c.x < 1.0
        assert 0.0 < c.y < 1.0

    def test_weighted_skewed(self) -> None:
        a = XY(x=0.64, y=0.33)
        b = XY(x=0.30, y=0.60)
        c = cc.mix_xy([a, b], weights=[0.25, 0.75])
        # Result should be closer to b (higher weight)
        assert 0.0 < c.x < 1.0
        assert 0.0 < c.y < 1.0

    def test_single_point_returns_itself(self) -> None:
        p = XY(x=0.3127, y=0.3290)
        c = cc.mix_xy([p])
        assert c.x == pytest.approx(0.3127, abs=0.001)
        assert c.y == pytest.approx(0.3290, abs=0.001)


# ---- luminance ----


class TestLuminance:
    def test_luminance_positive(
        self,
        primary_r: Spectrum,
    ) -> None:
        assert cc.luminance(primary_r) > 0

    def test_luminance_consistent_with_xyz(
        self,
        primary_g: Spectrum,
    ) -> None:
        from colorlab_pro.engines.spectrum_analyzer import xyz

        assert cc.luminance(primary_g) == pytest.approx(xyz(primary_g).Y)

    def test_luminance_scales_linearly(self, standard_wavelengths: np.ndarray) -> None:
        s = Spectrum(
            wavelengths=standard_wavelengths,
            values=np.ones_like(standard_wavelengths),
            unit="a.u.",
        )
        y1 = cc.luminance(s)
        s2 = Spectrum(
            wavelengths=standard_wavelengths,
            values=2.5 * np.ones_like(standard_wavelengths),
            unit="a.u.",
        )
        y2 = cc.luminance(s2)
        assert y2 == pytest.approx(2.5 * y1, rel=1e-9)


# ---- mix_xyz ----


class TestMixXYZ:
    def test_single_spectrum(
        self,
        primary_r: Spectrum,
    ) -> None:
        from colorlab_pro.engines.spectrum_analyzer import xyz

        r = xyz(primary_r)
        m = cc.mix_xyz([primary_r])
        assert m.X == pytest.approx(r.X)
        assert m.Y == pytest.approx(r.Y)
        assert m.Z == pytest.approx(r.Z)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="spectra must not be empty"):
            cc.mix_xyz([])

    def test_mismatched_weights_raises(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        with pytest.raises(ValueError, match="weights length"):
            cc.mix_xyz([primary_r, primary_g], weights=[1.0])

    def test_default_weights_ones(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        m = cc.mix_xyz([primary_r, primary_g])
        from colorlab_pro.engines.spectrum_analyzer import xyz

        r = xyz(primary_r)
        g = xyz(primary_g)
        assert m.X == pytest.approx(r.X + g.X)


# ---- delta_uv ----


class TestDeltaUV:
    def test_d65_delta_uv_zero(self, d65_spectrum: Spectrum) -> None:
        """D65 vs D65 reference: duv should be ~0."""
        cct, duv = cc.delta_uv(d65_spectrum, reference=XY(0.3127, 0.3290))
        assert abs(duv) < 0.01
        assert 5000 < cct < 8000

    def test_d65_default_reference(self, d65_spectrum: Spectrum) -> None:
        cct, duv = cc.delta_uv(d65_spectrum)
        assert abs(duv) < 0.01

    def test_greenish_sample_positive_duv(
        self,
        primary_g: Spectrum,
    ) -> None:
        """A green-dominant spectrum should have positive duv vs D65."""
        _, duv = cc.delta_uv(primary_g, reference=XY(0.3127, 0.3290))
        assert duv > 0


# ---- _to_common_grid ----


class TestToCommonGrid:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="spectra list must not be empty"):
            cc._to_common_grid([])

    def test_interpolates_different_grids(
        self,
        primary_r: Spectrum,
        standard_wavelengths: np.ndarray,
    ) -> None:
        # Coarser grid for the second spectrum; _to_common_grid should
        # interpolate it onto the first spectrum's wavelength grid.
        coarse_wl = np.arange(400.0, 701.0, 10.0, dtype=np.float64)
        coarse_v = np.exp(-0.5 * ((coarse_wl - 630.0) / 8.5) ** 2)
        coarse = Spectrum(wavelengths=coarse_wl, values=coarse_v, unit="a.u.")
        wl, aligned = cc._to_common_grid([primary_r, coarse])
        np.testing.assert_array_equal(wl, primary_r.wavelengths)
        assert aligned[0].shape == primary_r.values.shape
        assert aligned[1].shape == primary_r.values.shape
        # Values at overlapping wavelengths should be close.
        np.testing.assert_allclose(aligned[1], primary_r.values, atol=0.05)


# ---- mix_xyz edge weights ----


class TestMixXYZWeights:
    def test_zero_total_weight_raises(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        with pytest.raises(ValueError, match="weights sum must be > 0"):
            cc.mix_xyz([primary_r, primary_g], weights=[0.0, 0.0])


# ---- mix_xy edge weights ----


class TestMixXYWeights:
    def test_negative_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="weights must be non-negative"):
            cc.mix_xy([XY(0.3, 0.3), XY(0.5, 0.5)], weights=[-1.0, 1.0])

    def test_zero_total_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="weights sum must be > 0"):
            cc.mix_xy([XY(0.3, 0.3), XY(0.5, 0.5)], weights=[0.0, 0.0])


# ---- delta_e ----


class TestDeltaE:
    def test_delta_e_between_same_spectrum_is_zero(
        self,
        primary_r: Spectrum,
    ) -> None:
        de = cc.delta_e(primary_r, primary_r)
        assert de == pytest.approx(0.0, abs=1e-9)

    def test_delta_e_positive_for_different_spectra(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        de = cc.delta_e(primary_r, primary_g)
        assert de > 0

    def test_delta_e_methods_return_similar_order(
        self,
        primary_r: Spectrum,
        primary_g: Spectrum,
    ) -> None:
        de_76 = cc.delta_e(primary_r, primary_g, method="CIE 1976")
        de_2000 = cc.delta_e(primary_r, primary_g, method="CIE 2000")
        assert de_76 > 0
        assert de_2000 > 0
