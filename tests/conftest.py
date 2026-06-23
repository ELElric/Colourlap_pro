"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.spectrum import Spectrum


@pytest.fixture
def standard_wavelengths() -> np.ndarray:
    """380-780 nm, 1 nm step, 401 points."""
    return np.arange(380.0, 781.0, 1.0, dtype=np.float64)


@pytest.fixture
def gaussian_spectrum(standard_wavelengths: np.ndarray) -> Spectrum:
    """A simple Gaussian-like spectrum peaked at 550 nm."""
    x = standard_wavelengths
    peak = 550.0
    sigma = 20.0
    values = np.exp(-0.5 * ((x - peak) / sigma) ** 2)
    return Spectrum(wavelengths=x, values=values, unit="a.u.")


@pytest.fixture
def led_r_spectrum(standard_wavelengths: np.ndarray) -> Spectrum:
    """Narrow R-LED spectrum (peak 630 nm, FWHM ~20 nm)."""
    x = standard_wavelengths
    peak = 630.0
    sigma = 8.5  # FWHM ~20 nm
    values = np.exp(-0.5 * ((x - peak) / sigma) ** 2)
    return Spectrum(wavelengths=x, values=values, unit="a.u.")


@pytest.fixture
def led_g_spectrum(standard_wavelengths: np.ndarray) -> Spectrum:
    """Narrow G-LED spectrum (peak 530 nm, FWHM ~30 nm)."""
    x = standard_wavelengths
    peak = 530.0
    sigma = 12.7
    values = np.exp(-0.5 * ((x - peak) / sigma) ** 2)
    return Spectrum(wavelengths=x, values=values, unit="a.u.")


@pytest.fixture
def led_b_spectrum(standard_wavelengths: np.ndarray) -> Spectrum:
    """Narrow B-LED spectrum (peak 450 nm, FWHM ~20 nm)."""
    x = standard_wavelengths
    peak = 450.0
    sigma = 8.5
    values = np.exp(-0.5 * ((x - peak) / sigma) ** 2)
    return Spectrum(wavelengths=x, values=values, unit="a.u.")


@pytest.fixture
def rcf_spectrum(standard_wavelengths: np.ndarray) -> Spectrum:
    """Broadband red color filter (peak ~650 nm, FWHM ~80 nm)."""
    x = standard_wavelengths
    peak = 650.0
    sigma = 34.0
    values = np.exp(-0.5 * ((x - peak) / sigma) ** 2)
    return Spectrum(wavelengths=x, values=values, unit="a.u.")


@pytest.fixture
def spectrum_with_gap(standard_wavelengths: np.ndarray) -> Spectrum:
    """Spectrum with a small NaN gap (3 points)."""
    x = standard_wavelengths.copy()
    y = np.exp(-0.5 * ((x - 550.0) / 20.0) ** 2)
    y[200:203] = np.nan  # 3-point NaN gap near 580 nm
    return Spectrum(wavelengths=x, values=y, unit="a.u.")


@pytest.fixture
def spectrum_irregular_step() -> Spectrum:
    """Spectrum on a 5 nm grid (irregular but valid)."""
    wl = np.arange(380.0, 781.0, 5.0, dtype=np.float64)
    values = np.exp(-0.5 * ((wl - 550.0) / 20.0) ** 2)
    return Spectrum(wavelengths=wl, values=values, unit="a.u.")


@pytest.fixture
def seed_rng() -> None:
    """Fix numpy random seed for reproducible tests."""
    np.random.seed(42)


@pytest.fixture
def d65_spectrum(standard_wavelengths: np.ndarray) -> Spectrum:
    """Build a D65 illuminant spectrum (380-780 nm, 1 nm step)."""
    import colour

    d65 = colour.SDS_ILLUMINANTS["D65"]
    wl = standard_wavelengths
    v = np.array(
        [
            float(d65[np.float64(w)]) if d65.wavelengths[0] <= w <= d65.wavelengths[-1] else 0.0
            for w in wl
        ]
    )
    return Spectrum(wavelengths=wl, values=v, unit="a.u.")


@pytest.fixture
def equal_energy_spectrum(standard_wavelengths: np.ndarray) -> Spectrum:
    """A flat (constant) spectrum — yields E white (1/3, 1/3)."""
    return Spectrum(
        wavelengths=standard_wavelengths,
        values=np.ones_like(standard_wavelengths),
        unit="a.u.",
    )
