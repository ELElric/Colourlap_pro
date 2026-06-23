"""SpectrumNormalizer Engine.

Provides functions to normalize, interpolate, fill gaps, and detect the
channel type of a Spectrum.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline, PchipInterpolator
from scipy.signal import find_peaks

from colorlab_pro.dto.spectrum import Spectrum

# Channel type constants — only R, G, B
CHANNEL_UNKNOWN = "unknown"
CHANNEL_R = "R"
CHANNEL_G = "G"
CHANNEL_B = "B"

# Spectrum category constants
CATEGORY_CF = "CF"
CATEGORY_QD = "QD"
CATEGORY_LED = "LED"
CATEGORY_WHITE = "白光"
CATEGORY_UNKNOWN = "Unknown"

# Channel to category mapping.
# R/G/B channels map to LED by default. CF channels (RCF/GCF/BCF) map to CF.
# The actual category should be determined by the caller based on context
# (e.g. whether the spectrum is a color filter transmittance curve or an
# LED/QD emission spectrum). This mapping is a fallback only.
_CHANNEL_TO_CATEGORY: dict[str, str] = {
    CHANNEL_R: CATEGORY_LED,
    CHANNEL_G: CATEGORY_LED,
    CHANNEL_B: CATEGORY_LED,
    "RCF": CATEGORY_CF,
    "GCF": CATEGORY_CF,
    "BCF": CATEGORY_CF,
    "W": CATEGORY_WHITE,
    "WLED": CATEGORY_WHITE,
}

# Wavelength bands for RGB detection
_BAND_R = (600.0, 700.0)
_BAND_G = (500.0, 580.0)
_BAND_B = (400.0, 500.0)


def normalize(spectrum: Spectrum, mode: Literal["peak", "area"] = "peak") -> Spectrum:
    """Normalize a spectrum.

    Args:
        spectrum: Input spectrum.
        mode: Normalization mode.
            - "peak": divide by max value.
            - "area": divide by integral (trapezoidal).

    Returns:
        New Spectrum with normalized values. Unit becomes "a.u.".
    """
    if spectrum.values.size == 0:
        raise ValueError("Cannot normalize an empty spectrum.")
    if mode == "peak":
        peak = float(np.max(spectrum.values))
        if peak == 0:
            raise ValueError("Cannot peak-normalize a zero spectrum.")
        new_values = spectrum.values / peak
    elif mode == "area":
        # numpy<2.0 uses np.trapz; numpy>=2.0 uses np.trapezoid
        if hasattr(np, "trapezoid"):
            area = float(np.trapezoid(spectrum.values, spectrum.wavelengths))
        else:
            area = float(np.trapz(spectrum.values, spectrum.wavelengths))
        if area == 0:
            raise ValueError("Cannot area-normalize a zero-integral spectrum.")
        new_values = spectrum.values / area
    else:
        raise ValueError(f"Unknown normalize mode: {mode!r}")
    return Spectrum(
        wavelengths=spectrum.wavelengths.copy(),
        values=new_values,
        unit="a.u.",
        meta={**spectrum.meta, "normalize": mode},
    )


def interpolate(
    spectrum: Spectrum,
    step: int = 1,
    method: Literal["cubic", "pchip"] = "cubic",
) -> Spectrum:
    """Interpolate a spectrum to a regular wavelength grid.

    Args:
        spectrum: Input spectrum with potentially irregular step.
        step: Output step in nm. Default 1.
        method: "cubic" (CubicSpline) or "pchip" (PCHIP).

    Returns:
        New Spectrum on a regular wavelength grid.
    """
    if step <= 0:
        raise ValueError("step must be positive.")
    if spectrum.wavelengths.size < 2:
        raise ValueError("Need at least 2 points to interpolate.")
    wl_min = float(spectrum.wavelengths[0])
    wl_max = float(spectrum.wavelengths[-1])
    new_wl = np.arange(wl_min, wl_max + step / 2.0, step, dtype=np.float64)
    if method == "cubic":
        cs = CubicSpline(spectrum.wavelengths, spectrum.values)
        new_values = cs(new_wl)
    elif method == "pchip":
        pi = PchipInterpolator(spectrum.wavelengths, spectrum.values)
        new_values = pi(new_wl)
    else:
        raise ValueError(f"Unknown interpolation method: {method!r}")
    return Spectrum(
        wavelengths=new_wl,
        values=np.asarray(new_values, dtype=np.float64),
        unit=spectrum.unit,
        meta={**spectrum.meta, "interpolation": method, "step_nm": step},
    )


STANDARD_WAVELENGTH_START: float = 380.0
STANDARD_WAVELENGTH_END: float = 780.0


def align_to_standard_range(
    spectrum: Spectrum,
    start: float = STANDARD_WAVELENGTH_START,
    end: float = STANDARD_WAVELENGTH_END,
    fill_value: float = 0.0,
) -> Spectrum:
    """Align a spectrum to the standard wavelength range.

    The output spectrum has wavelengths from ``start`` to ``end`` inclusive,
    using the same step as the input where possible. Values within the
    original range are interpolated linearly; values outside are filled with
    ``fill_value``.

    Args:
        spectrum: Input spectrum.
        start: Start wavelength (nm). Default 380.
        end: End wavelength (nm). Default 780.
        fill_value: Value to use for wavelengths outside the input range.

    Returns:
        New Spectrum aligned to [start, end].
    """
    # Preserve original step if the input grid is regular; otherwise use 1 nm.
    if spectrum.wavelengths.size >= 2:
        steps = np.diff(spectrum.wavelengths)
        step = float(np.min(steps[steps > 0])) if np.any(steps > 0) else 1.0
        # Fall back to 1 nm if the grid is highly irregular.
        if steps.size > 1 and float(np.max(steps)) / step > 2.0:
            step = 1.0
    else:
        step = 1.0
    if step <= 0:
        step = 1.0

    # Ensure the grid includes exact integer wavelengths when step == 1.
    new_wl = np.arange(start, end + step / 2.0, step, dtype=np.float64)

    if spectrum.wavelengths.size < 2:
        # Degenerate single-point spectrum: place the value at the nearest
        # standard wavelength and fill the rest with zeros.
        new_values = np.full_like(new_wl, fill_value)
        if spectrum.wavelengths.size == 1:
            idx = int(np.argmin(np.abs(new_wl - spectrum.wavelengths[0])))
            new_values[idx] = spectrum.values[0]
    else:
        # Linear interpolation for points inside the original range.
        new_values = np.interp(
            new_wl,
            spectrum.wavelengths,
            spectrum.values,
            left=fill_value,
            right=fill_value,
        )

    return Spectrum(
        wavelengths=new_wl,
        values=np.asarray(new_values, dtype=np.float64),
        unit=spectrum.unit,
        meta={
            **spectrum.meta,
            "aligned_range": (float(start), float(end)),
            "original_range": (float(spectrum.wavelengths[0]), float(spectrum.wavelengths[-1])),
        },
    )


def auto_fill_gaps(
    spectrum: Spectrum,
    fill_value: float = 0.0,
    min_gap_nm: float = 5.0,
) -> Spectrum:
    """Fill small gaps (NaN values) in a spectrum by linear interpolation.

    Args:
        spectrum: Input spectrum (may contain NaN).
        fill_value: Value to use at the edges if the gap touches an end.
        min_gap_nm: Maximum gap size (nm) to auto-fill; larger gaps are
            left as NaN.

    Returns:
        New Spectrum with small NaN runs replaced.
    """
    wl = spectrum.wavelengths
    vals = spectrum.values
    if not np.any(np.isnan(vals)):
        return spectrum
    new_vals = vals.copy()
    isnan = np.isnan(vals)
    # find runs of NaN
    changes = np.diff(isnan.astype(int))
    starts = np.where(changes == 1)[0] + 1
    ends = np.where(changes == -1)[0] + 1
    if isnan[0]:
        starts = np.concatenate(([0], starts))
    if isnan[-1]:
        ends = np.concatenate((ends, [vals.size]))
    for s, e in zip(starts, ends, strict=True):
        if s == 0 or e == vals.size:
            new_vals[s:e] = fill_value
            continue
        wl_left = wl[s - 1]
        wl_right = wl[e]
        if (wl_right - wl_left) > min_gap_nm:
            continue
        v_left = vals[s - 1]
        v_right = vals[e]
        t = (wl[s:e] - wl_left) / (wl_right - wl_left)
        new_vals[s:e] = v_left + (v_right - v_left) * t
    return Spectrum(
        wavelengths=wl.copy(),
        values=new_vals,
        unit=spectrum.unit,
        meta={**spectrum.meta, "auto_fill_gaps": True},
    )


def _find_peak(wavelengths: NDArray[np.float64], values: NDArray[np.float64]) -> float:
    return float(wavelengths[int(np.argmax(values))])


def _fwhm(wavelengths: NDArray[np.float64], values: NDArray[np.float64]) -> float:
    """Compute the full width at half maximum in nm."""
    peak_v = float(np.max(values))
    if peak_v <= 0:
        return float("nan")
    half = peak_v / 2.0
    peak_idx = int(np.argmax(values))
    # walk left
    left = peak_idx
    while left > 0 and values[left] > half:
        left -= 1
    # walk right
    right = peak_idx
    while right < values.size - 1 and values[right] > half:
        right += 1
    return float(wavelengths[right] - wavelengths[left])


def _band_max(
    wavelengths: NDArray[np.float64], values: NDArray[np.float64], band: tuple[float, float]
) -> float:
    """Return the maximum value within a wavelength band."""
    mask = (wavelengths >= band[0]) & (wavelengths <= band[1])
    if not np.any(mask):
        return 0.0
    return float(np.max(values[mask]))


def _detect_white(spectrum: Spectrum, threshold: float = 0.3) -> bool:
    """Detect whether a spectrum looks like white light.

    A white spectrum has significant peaks in all R/G/B bands.
    ``threshold`` is the minimum ratio to the global peak.
    """
    if spectrum.values.size < 3:
        return False
    global_peak = float(np.max(spectrum.values))
    if global_peak <= 0:
        return False
    r_max = _band_max(spectrum.wavelengths, spectrum.values, _BAND_R)
    g_max = _band_max(spectrum.wavelengths, spectrum.values, _BAND_G)
    b_max = _band_max(spectrum.wavelengths, spectrum.values, _BAND_B)
    return (
        r_max / global_peak >= threshold
        and g_max / global_peak >= threshold
        and b_max / global_peak >= threshold
    )


def _find_peak_in_band(
    wavelengths: NDArray[np.float64], values: NDArray[np.float64], band: tuple[float, float]
) -> tuple[float, float]:
    """Return (wavelength, value) of the strongest peak within a band.

    Uses scipy.signal.find_peaks to locate local maxima and returns the
    highest one. If no peak is found, the maximum value point is returned.
    """
    mask = (wavelengths >= band[0]) & (wavelengths <= band[1])
    if not np.any(mask):
        return 0.0, 0.0
    wl_band = wavelengths[mask]
    val_band = values[mask]
    # Smooth-aware peak detection; require a minimal prominence to avoid noise.
    peaks, properties = find_peaks(val_band, prominence=float(np.max(val_band)) * 0.05)
    if peaks.size == 0:
        idx = int(np.argmax(val_band))
        return float(wl_band[idx]), float(val_band[idx])
    peak_idx = int(peaks[int(np.argmax(properties["prominences"]))])
    return float(wl_band[peak_idx]), float(val_band[peak_idx])


def _is_multi_peak(spectrum: Spectrum, min_peaks: int = 2, prominence_ratio: float = 0.25) -> bool:
    """Return True if the spectrum has multiple significant peaks.

    A spectrum is considered multi-peak when at least ``min_peaks`` peaks are
    found and the second-highest peak prominence is at least
    ``prominence_ratio`` of the highest peak prominence.
    """
    if spectrum.values.size < 5:
        return False
    peaks, properties = find_peaks(spectrum.values, prominence=0.0)
    if peaks.size < min_peaks:
        return False
    prominences = properties["prominences"]
    sorted_prominences = np.sort(prominences)[::-1]
    return (
        sorted_prominences.size >= 2
        and float(sorted_prominences[1]) >= float(sorted_prominences[0]) * prominence_ratio
    )


def _fwhm_in_band(
    wavelengths: NDArray[np.float64], values: NDArray[np.float64], band: tuple[float, float]
) -> float:
    """Compute FWHM for the strongest peak within a wavelength band.

    The band is masked out; values outside the band are treated as zero.
    """
    masked_values = np.where((wavelengths >= band[0]) & (wavelengths <= band[1]), values, 0.0)
    return _fwhm(wavelengths, masked_values)


def detect_channel(spectrum: Spectrum) -> str:
    """Detect the channel type of a spectrum.

    Detection is driven primarily by the **peak intensity / transmittance**
    in the R/G/B bands:
        1. Find the dominant band by maximum value.
        2. Within that band, locate the strongest peak.
        3. Classify by peak wavelength and FWHM:
           - FWHM <= 30: narrow band LED
           - FWHM 30-50: medium band QD
           - FWHM >= 50: broadband CF

    For multi-peak spectra only the R and G bands are considered, matching
    the practical behavior of some LED/QD sources with secondary lobes.
    """
    if spectrum.values.size < 3:
        return CHANNEL_UNKNOWN

    # Multi-peak handling: only consider R and G bands.
    if _is_multi_peak(spectrum):
        r_peak, r_val = _find_peak_in_band(spectrum.wavelengths, spectrum.values, _BAND_R)
        g_peak, g_val = _find_peak_in_band(spectrum.wavelengths, spectrum.values, _BAND_G)
        if r_val == 0 and g_val == 0:
            return CHANNEL_UNKNOWN
        if r_val >= g_val:
            return CHANNEL_R
        return CHANNEL_G

    # Find dominant band by peak intensity / transmittance.
    r_peak, r_val = _find_peak_in_band(spectrum.wavelengths, spectrum.values, _BAND_R)
    g_peak, g_val = _find_peak_in_band(spectrum.wavelengths, spectrum.values, _BAND_G)
    b_peak, b_val = _find_peak_in_band(spectrum.wavelengths, spectrum.values, _BAND_B)

    if r_val == 0 and g_val == 0 and b_val == 0:
        return CHANNEL_UNKNOWN

    # Determine the overall peak wavelength
    peak_idx = int(np.argmax(spectrum.values))
    peak_nm = float(spectrum.wavelengths[peak_idx])

    # Check if peak falls within a recognized band
    in_r = _BAND_R[0] <= peak_nm <= _BAND_R[1]
    in_g = _BAND_G[0] <= peak_nm <= _BAND_G[1]
    in_b = _BAND_B[0] <= peak_nm <= _BAND_B[1]

    if not in_r and not in_g and not in_b:
        return CHANNEL_UNKNOWN

    if r_val >= g_val and r_val >= b_val and in_r:
        return CHANNEL_R
    elif g_val >= r_val and g_val >= b_val and in_g:
        return CHANNEL_G
    elif b_val >= r_val and b_val >= g_val and in_b:
        return CHANNEL_B

    return CHANNEL_UNKNOWN


def detect_category(spectrum: Spectrum) -> str:
    """Detect the category of a spectrum.

    Returns Unknown by default — category should be set by the user
    at import time (LED / CF / QD / 白光).
    """
    return CATEGORY_UNKNOWN


def category_from_channel(channel: str | None) -> str:
    """Return category for a known channel, or Unknown."""
    if channel is None:
        return CATEGORY_UNKNOWN
    return _CHANNEL_TO_CATEGORY.get(channel, CATEGORY_UNKNOWN)
