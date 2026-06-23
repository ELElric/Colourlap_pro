"""Unit tests for colorlab_pro.engines.spectrum_normalizer (T-02)."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.spectrum_normalizer import (
    CATEGORY_LED,
    CATEGORY_UNKNOWN,
    CHANNEL_B,
    CHANNEL_G,
    CHANNEL_R,
    CHANNEL_UNKNOWN,
    _band_max,
    _detect_white,
    _find_peak,
    _find_peak_in_band,
    _fwhm,
    _fwhm_in_band,
    _is_multi_peak,
    align_to_standard_range,
    auto_fill_gaps,
    category_from_channel,
    detect_category,
    detect_channel,
    interpolate,
    normalize,
)

# ---------------- align_to_standard_range ----------------


class TestAlignToStandardRange:
    def test_full_range_unchanged(self, gaussian_spectrum: Spectrum) -> None:
        s = align_to_standard_range(gaussian_spectrum)
        assert s.wavelengths[0] == pytest.approx(380.0)
        assert s.wavelengths[-1] == pytest.approx(780.0)
        assert s.wavelengths.size == 401

    def test_short_range_filled_with_zeros(self, standard_wavelengths: np.ndarray) -> None:
        x = standard_wavelengths[50:351]  # 430-730 nm
        y = np.exp(-0.5 * ((x - 550.0) / 20.0) ** 2)
        s = Spectrum(wavelengths=x, values=y, unit="a.u.")
        aligned = align_to_standard_range(s)
        assert aligned.wavelengths[0] == pytest.approx(380.0)
        assert aligned.wavelengths[-1] == pytest.approx(780.0)
        assert aligned.wavelengths.size == 401
        # Outside original range should be zero
        assert aligned.values[0] == pytest.approx(0.0)
        assert aligned.values[-1] == pytest.approx(0.0)
        # Inside should be non-zero
        idx_550 = int(np.argmin(np.abs(aligned.wavelengths - 550.0)))
        assert aligned.values[idx_550] > 0.5

    def test_preserves_step(self, spectrum_irregular_step: Spectrum) -> None:
        aligned = align_to_standard_range(spectrum_irregular_step)
        # Original step is 5 nm
        assert np.allclose(np.diff(aligned.wavelengths), 5.0)

    def test_original_values_preserved(self, standard_wavelengths: np.ndarray) -> None:
        y = np.exp(-0.5 * ((standard_wavelengths - 550.0) / 20.0) ** 2)
        s = Spectrum(wavelengths=standard_wavelengths, values=y, unit="a.u.")
        aligned = align_to_standard_range(s)
        np.testing.assert_allclose(aligned.values, s.values, atol=1e-10)


# ---------------- normalize ----------------


class TestNormalize:
    def test_peak_normalization(self, gaussian_spectrum: Spectrum) -> None:
        s = normalize(gaussian_spectrum, mode="peak")
        assert s.values.max() == pytest.approx(1.0)
        assert s.unit == "a.u."

    def test_area_normalization(self, gaussian_spectrum: Spectrum) -> None:
        s = normalize(gaussian_spectrum, mode="area")
        if hasattr(np, "trapezoid"):
            area = float(np.trapezoid(s.values, s.wavelengths))
        else:
            area = float(np.trapz(s.values, s.wavelengths))
        assert area == pytest.approx(1.0)

    def test_zero_spectrum_raises(self) -> None:
        wl = np.arange(380.0, 781.0)
        z = Spectrum(wavelengths=wl, values=np.zeros_like(wl))
        with pytest.raises(ValueError, match="zero spectrum"):
            normalize(z, mode="peak")
        with pytest.raises(ValueError, match="zero"):
            normalize(z, mode="area")

    def test_unknown_mode_raises(self, gaussian_spectrum: Spectrum) -> None:
        with pytest.raises(ValueError, match="Unknown normalize mode"):
            normalize(gaussian_spectrum, mode="bogus")  # type: ignore[arg-type]

    def test_preserves_wavelengths(self, gaussian_spectrum: Spectrum) -> None:
        s = normalize(gaussian_spectrum, mode="peak")
        np.testing.assert_array_equal(s.wavelengths, gaussian_spectrum.wavelengths)


# ---------------- interpolate ----------------


class TestInterpolate:
    def test_5nm_to_1nm_cubic(self, spectrum_irregular_step: Spectrum) -> None:
        s = interpolate(spectrum_irregular_step, step=1, method="cubic")
        assert s.wavelengths[0] == pytest.approx(380.0)
        assert s.wavelengths[-1] == pytest.approx(780.0)
        assert s.wavelengths.size == 401
        # value at original 550 nm should be near 1.0
        idx_550 = int(np.argmin(np.abs(s.wavelengths - 550.0)))
        assert s.values[idx_550] == pytest.approx(1.0, abs=1e-6)

    def test_5nm_to_1nm_pchip(self, spectrum_irregular_step: Spectrum) -> None:
        s = interpolate(spectrum_irregular_step, step=1, method="pchip")
        assert s.wavelengths.size == 401
        assert np.all(np.isfinite(s.values))

    def test_invalid_step_raises(self, spectrum_irregular_step: Spectrum) -> None:
        with pytest.raises(ValueError, match="step must be positive"):
            interpolate(spectrum_irregular_step, step=0)

    def test_unknown_method_raises(self, spectrum_irregular_step: Spectrum) -> None:
        with pytest.raises(ValueError, match="Unknown interpolation method"):
            interpolate(spectrum_irregular_step, method="linear")  # type: ignore[arg-type]

    def test_interpolation_smoothness(self, spectrum_irregular_step: Spectrum) -> None:
        s = interpolate(spectrum_irregular_step, step=1, method="cubic")
        # No unexpected spikes: max finite derivative should be bounded
        diffs = np.diff(s.values)
        assert np.max(np.abs(diffs)) < 0.1


# ---------------- auto_fill_gaps ----------------


class TestAutoFillGaps:
    def test_fills_small_gap(self, spectrum_with_gap: Spectrum) -> None:
        s = auto_fill_gaps(spectrum_with_gap)
        assert not np.any(np.isnan(s.values))
        # filled values around 580 nm should be ~ continuous with neighbors
        idx = np.where((s.wavelengths > 575) & (s.wavelengths < 585))[0]
        # local std should be small (< 0.1 to accommodate the slope around 580 nm
        # on a Gaussian peaked at 550 nm with sigma 20 nm)
        assert np.std(s.values[idx]) < 0.1

    def test_leaves_large_gap(self, standard_wavelengths: np.ndarray) -> None:
        y = np.exp(-0.5 * ((standard_wavelengths - 550.0) / 20.0) ** 2)
        y[100:200] = np.nan  # 100-point gap
        s = Spectrum(wavelengths=standard_wavelengths, values=y)
        filled = auto_fill_gaps(s, min_gap_nm=20.0)
        assert np.any(np.isnan(filled.values))

    def test_no_gap_returns_equivalent(self, gaussian_spectrum: Spectrum) -> None:
        s = auto_fill_gaps(gaussian_spectrum)
        np.testing.assert_array_equal(s.values, gaussian_spectrum.values)

    def test_edge_nan_uses_fill_value(self, standard_wavelengths: np.ndarray) -> None:
        y = np.exp(-0.5 * ((standard_wavelengths - 550.0) / 20.0) ** 2)
        y[:5] = np.nan
        s = Spectrum(wavelengths=standard_wavelengths, values=y)
        filled = auto_fill_gaps(s, fill_value=0.0)
        assert filled.values[0] == 0.0
        assert filled.values[4] == 0.0


# ---------------- detect_channel ----------------


class TestDetectChannel:
    def test_red_led(self, led_r_spectrum: Spectrum) -> None:
        assert detect_channel(led_r_spectrum) == CHANNEL_R

    def test_green_led(self, led_g_spectrum: Spectrum) -> None:
        assert detect_channel(led_g_spectrum) == CHANNEL_G

    def test_blue_led(self, led_b_spectrum: Spectrum) -> None:
        assert detect_channel(led_b_spectrum) == CHANNEL_B

    def test_rcf(self, rcf_spectrum: Spectrum) -> None:
        assert detect_channel(rcf_spectrum) == CHANNEL_R

    def test_green_led_with_broader_fwhm_is_qd(self, standard_wavelengths: np.ndarray) -> None:
        # 35 nm FWHM
        x = standard_wavelengths
        values = np.exp(-0.5 * ((x - 530.0) / 15.0) ** 2)
        s = Spectrum(wavelengths=x, values=values)
        assert detect_channel(s) in (CHANNEL_G, CHANNEL_R)

    def test_too_short_returns_unknown(self) -> None:
        wl = np.array([550.0, 551.0])
        v = np.array([0.1, 0.2])
        s = Spectrum(wavelengths=wl, values=v)
        assert detect_channel(s) == "unknown"

    def test_zero_spectrum_returns_unknown(self, standard_wavelengths: np.ndarray) -> None:
        s = Spectrum(
            wavelengths=standard_wavelengths,
            values=np.zeros_like(standard_wavelengths),
        )
        assert detect_channel(s) == "unknown"

    def test_multi_peak_prefers_r_band(self, standard_wavelengths: np.ndarray) -> None:
        # Multi-peak spectrum with a strong R peak and a weaker G peak.
        x = standard_wavelengths
        r = 0.8 * np.exp(-0.5 * ((x - 630.0) / 15.0) ** 2)
        g = 0.3 * np.exp(-0.5 * ((x - 530.0) / 15.0) ** 2)
        s = Spectrum(wavelengths=x, values=r + g, unit="a.u.")
        assert detect_channel(s) == CHANNEL_R

    def test_multi_peak_prefers_g_band(self, standard_wavelengths: np.ndarray) -> None:
        # Multi-peak spectrum with a strong G peak and a weaker R peak.
        x = standard_wavelengths
        r = 0.3 * np.exp(-0.5 * ((x - 630.0) / 15.0) ** 2)
        g = 0.8 * np.exp(-0.5 * ((x - 530.0) / 15.0) ** 2)
        s = Spectrum(wavelengths=x, values=r + g, unit="a.u.")
        assert detect_channel(s) == CHANNEL_G


# ---------------- detect_category ----------------


class TestDetectCategory:
    def test_r_led_returns_unknown(self, led_r_spectrum: Spectrum) -> None:
        assert detect_category(led_r_spectrum) == CATEGORY_UNKNOWN

    def test_g_led_returns_unknown(self, led_g_spectrum: Spectrum) -> None:
        assert detect_category(led_g_spectrum) == CATEGORY_UNKNOWN

    def test_b_led_returns_unknown(self, led_b_spectrum: Spectrum) -> None:
        assert detect_category(led_b_spectrum) == CATEGORY_UNKNOWN

    def test_rcf_returns_unknown(self, rcf_spectrum: Spectrum) -> None:
        assert detect_category(rcf_spectrum) == CATEGORY_UNKNOWN

    def test_white_spectrum_returns_unknown(self, standard_wavelengths: np.ndarray) -> None:
        x = standard_wavelengths
        r = np.exp(-0.5 * ((x - 630.0) / 20.0) ** 2)
        g = np.exp(-0.5 * ((x - 530.0) / 20.0) ** 2)
        b = np.exp(-0.5 * ((x - 450.0) / 20.0) ** 2)
        s = Spectrum(wavelengths=x, values=r + g + b, unit="a.u.")
        assert detect_category(s) == CATEGORY_UNKNOWN

    def test_zero_spectrum_returns_unknown_category(self, standard_wavelengths: np.ndarray) -> None:
        s = Spectrum(
            wavelengths=standard_wavelengths,
            values=np.zeros_like(standard_wavelengths),
        )
        assert detect_category(s) == CATEGORY_UNKNOWN


# ---------------- category_from_channel ----------------


class TestCategoryFromChannel:
    def test_known_channels(self) -> None:
        assert category_from_channel(CHANNEL_R) == CATEGORY_LED
        assert category_from_channel(CHANNEL_G) == CATEGORY_LED
        assert category_from_channel(CHANNEL_B) == CATEGORY_LED

    def test_unknown_channel(self) -> None:
        assert category_from_channel("foo") == CATEGORY_UNKNOWN

    def test_none_channel(self) -> None:
        assert category_from_channel(None) == CATEGORY_UNKNOWN


# ---------------- normalize edge cases ----------------


class TestNormalizeEdgeCases:
    def test_empty_spectrum_raises(self) -> None:
        s = Spectrum(wavelengths=np.array([]), values=np.array([]))
        with pytest.raises(ValueError, match="empty spectrum"):
            normalize(s, mode="peak")

    def test_zero_integral_area_raises(self, standard_wavelengths: np.ndarray) -> None:
        # Linear function symmetric around the midpoint => exact zero integral.
        y = standard_wavelengths - 580.0
        s = Spectrum(wavelengths=standard_wavelengths, values=y)
        with pytest.raises(ValueError, match="zero-integral"):
            normalize(s, mode="area")


# ---------------- interpolate edge cases ----------------


class TestInterpolateEdgeCases:
    def test_single_point_raises(self) -> None:
        s = Spectrum(wavelengths=np.array([550.0]), values=np.array([1.0]))
        with pytest.raises(ValueError, match="at least 2 points"):
            interpolate(s, step=1)


# ---------------- align_to_standard_range edge cases ----------------


class TestAlignToStandardRangeEdgeCases:
    def test_highly_irregular_uses_1nm_step(self, standard_wavelengths: np.ndarray) -> None:
        # Mix of 1 nm and 5 nm steps: max/min step ratio > 2 => fall back to 1 nm.
        wl = np.concatenate(
            [
                np.arange(380.0, 400.0, 1.0),
                np.arange(400.0, 781.0, 5.0),
            ]
        )
        y = np.exp(-0.5 * ((wl - 550.0) / 20.0) ** 2)
        s = Spectrum(wavelengths=wl, values=y)
        aligned = align_to_standard_range(s)
        assert np.allclose(np.diff(aligned.wavelengths), 1.0)

    def test_single_point_spectrum(self) -> None:
        s = Spectrum(wavelengths=np.array([550.0]), values=np.array([0.8]))
        aligned = align_to_standard_range(s)
        assert aligned.wavelengths.size == 401
        idx = int(np.argmin(np.abs(aligned.wavelengths - 550.0)))
        assert aligned.values[idx] == pytest.approx(0.8)
        assert aligned.values[0] == pytest.approx(0.0)
        assert aligned.values[-1] == pytest.approx(0.0)

    def test_zero_step_falls_back_to_1nm(self, standard_wavelengths: np.ndarray) -> None:
        # Duplicate wavelength produces a zero step; should be ignored.
        wl = standard_wavelengths.copy()
        wl[1] = wl[0]
        y = np.exp(-0.5 * ((standard_wavelengths - 550.0) / 20.0) ** 2)
        s = Spectrum(wavelengths=wl, values=y)
        aligned = align_to_standard_range(s)
        assert np.allclose(np.diff(aligned.wavelengths), 1.0)


# ---------------- auto_fill_gaps edge cases ----------------


class TestAutoFillGapsEdgeCases:
    def test_trailing_nan_uses_fill_value(self, standard_wavelengths: np.ndarray) -> None:
        y = np.exp(-0.5 * ((standard_wavelengths - 550.0) / 20.0) ** 2)
        y[-5:] = np.nan
        s = Spectrum(wavelengths=standard_wavelengths, values=y)
        filled = auto_fill_gaps(s, fill_value=0.0)
        assert filled.values[-1] == 0.0
        assert filled.values[-5] == 0.0


# ---------------- helper functions ----------------


class TestHelpers:
    def test_find_peak(self, standard_wavelengths: np.ndarray) -> None:
        y = np.exp(-0.5 * ((standard_wavelengths - 550.0) / 20.0) ** 2)
        assert _find_peak(standard_wavelengths, y) == pytest.approx(550.0)

    def test_fwhm_zero_peak(self, standard_wavelengths: np.ndarray) -> None:
        assert np.isnan(_fwhm(standard_wavelengths, np.zeros_like(standard_wavelengths)))

    def test_band_max_no_mask(self) -> None:
        wl = np.array([700.0, 710.0, 720.0])
        v = np.array([0.1, 0.2, 0.3])
        assert _band_max(wl, v, (400.0, 500.0)) == 0.0

    def test_detect_white_too_short(self) -> None:
        s = Spectrum(wavelengths=np.array([550.0]), values=np.array([1.0]))
        assert _detect_white(s) is False

    def test_is_multi_peak_too_short(self) -> None:
        s = Spectrum(wavelengths=np.array([550.0]), values=np.array([1.0]))
        assert _is_multi_peak(s) is False

    def test_fwhm_in_band(self, standard_wavelengths: np.ndarray) -> None:
        y = np.exp(-0.5 * ((standard_wavelengths - 550.0) / 20.0) ** 2)
        width = _fwhm_in_band(standard_wavelengths, y, (500.0, 600.0))
        assert width > 40.0

    def test_find_peak_in_band_no_overlap(self, standard_wavelengths: np.ndarray) -> None:
        peak, value = _find_peak_in_band(
            standard_wavelengths, np.ones_like(standard_wavelengths), (200.0, 300.0)
        )
        assert peak == 0.0
        assert value == 0.0


# ---------------- detect_channel classification branches ----------------


class TestDetectChannelBranches:
    def _make_gaussian(
        self,
        wavelengths: np.ndarray,
        peak: float,
        fwhm: float,
    ) -> Spectrum:
        sigma = fwhm / 2.355
        values = np.exp(-0.5 * ((wavelengths - peak) / sigma) ** 2)
        return Spectrum(wavelengths=wavelengths, values=values)

    def test_qd_red(self, standard_wavelengths: np.ndarray) -> None:
        s = self._make_gaussian(standard_wavelengths, 630.0, 35.0)
        assert detect_channel(s) == CHANNEL_R

    def test_rcf(self, standard_wavelengths: np.ndarray) -> None:
        s = self._make_gaussian(standard_wavelengths, 650.0, 80.0)
        assert detect_channel(s) == CHANNEL_R

    def test_qd_green(self, standard_wavelengths: np.ndarray) -> None:
        s = self._make_gaussian(standard_wavelengths, 530.0, 45.0)
        assert detect_channel(s) == CHANNEL_G

    def test_gcf(self, standard_wavelengths: np.ndarray) -> None:
        s = self._make_gaussian(standard_wavelengths, 550.0, 80.0)
        assert detect_channel(s) == CHANNEL_G

    def test_bcf(self, standard_wavelengths: np.ndarray) -> None:
        s = self._make_gaussian(standard_wavelengths, 470.0, 80.0)
        assert detect_channel(s) == CHANNEL_B

    def test_multi_peak_unknown_when_no_rg(self, standard_wavelengths: np.ndarray) -> None:
        # Multi-peak with two narrow B peaks and exact zeros outside B band.
        values = np.zeros_like(standard_wavelengths)
        mask_b = (standard_wavelengths >= 400.0) & (standard_wavelengths < 500.0)
        b1 = np.exp(-0.5 * ((standard_wavelengths[mask_b] - 440.0) / 5.0) ** 2)
        b2 = 0.8 * np.exp(-0.5 * ((standard_wavelengths[mask_b] - 470.0) / 5.0) ** 2)
        values[mask_b] = b1 + b2
        s = Spectrum(wavelengths=standard_wavelengths, values=values)
        assert detect_channel(s) == CHANNEL_UNKNOWN

    def test_fwhm_nan_fallback_uses_default_width(
        self, standard_wavelengths: np.ndarray, monkeypatch
    ) -> None:
        # Force _fwhm_in_band to return NaN so the defensive width fallback runs.
        monkeypatch.setattr(
            "colorlab_pro.engines.spectrum_normalizer._fwhm_in_band",
            lambda *_args, **_kwargs: float("nan"),
        )

        r = self._make_gaussian(standard_wavelengths, 630.0, 35.0)
        g = self._make_gaussian(standard_wavelengths, 530.0, 45.0)
        b = self._make_gaussian(standard_wavelengths, 450.0, 80.0)

        assert detect_channel(r) == CHANNEL_R
        assert detect_channel(g) == CHANNEL_G
        assert detect_channel(b) == CHANNEL_B

    def test_unknown_peak_outside_bands(self, standard_wavelengths: np.ndarray) -> None:
        s = self._make_gaussian(standard_wavelengths, 590.0, 30.0)
        assert detect_channel(s) == CHANNEL_UNKNOWN
