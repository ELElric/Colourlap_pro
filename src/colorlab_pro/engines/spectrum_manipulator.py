"""SpectrumManipulator Engine.

Provides transformation functions for emission spectra:

1. **Peak wavelength shift** (``translate_spectrum``):
   Shifts a spectrum along the wavelength axis by a given delta.

2. **FWHM scaling** (``scale_fwhm``):
   Scales the full-width half-maximum by raising normalised values to a
   power derived from the desired scaling factor.  For a Gaussian peak,
   raising to power *p* changes the FWHM by a factor of 1/√p.

3. **QD blue-leakage handling**:
   Quantum-dot spectra contain two components — blue leakage from the
   B-LED excitation and the QD emission peak at longer wavelengths.
   ``separate_qd_spectrum`` splits a QD spectrum into these two parts,
   ``recompose_qd_spectrum`` recombines them, and
   ``update_qd_blue_leakage`` updates the leakage when the B-LED
   spectrum is adjusted.

4. **Measurement helpers** (``peak_wavelength``, ``measure_fwhm``):
   Lightweight utilities to quantify peak position and width.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from colorlab_pro.dto.spectrum import Spectrum


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


def peak_wavelength(spectrum: Spectrum) -> float:
    """Return the wavelength at which the spectrum reaches its maximum.

    Args:
        spectrum: Input spectrum.

    Returns:
        Peak wavelength in nm.

    Raises:
        ValueError: If the spectrum is empty.
    """
    if spectrum.values.size == 0:
        raise ValueError("Cannot find peak of an empty spectrum")
    idx = int(np.argmax(spectrum.values))
    return float(spectrum.wavelengths[idx])


def measure_fwhm(spectrum: Spectrum) -> float:
    """Compute the full width at half maximum (FWHM) of a spectrum.

    Uses linear interpolation between sample points for sub-sample
    precision.

    Args:
        spectrum: Input spectrum.

    Returns:
        FWHM in nm. Returns 0.0 if the peak is at the edge or the
        half-max level is never crossed.
    """
    if spectrum.values.size < 2:
        return 0.0

    values = spectrum.values
    wavelengths = spectrum.wavelengths
    peak_val = float(np.max(values))
    if peak_val <= 0:
        return 0.0
    half_max = peak_val / 2.0

    peak_idx = int(np.argmax(values))

    # Search left of peak for half-max crossing.
    left_wl: float | None = None
    for i in range(peak_idx, 0, -1):
        if values[i] >= half_max and values[i - 1] < half_max:
            denom = values[i] - values[i - 1]
            if abs(denom) < 1e-15:
                left_wl = float(wavelengths[i])
            else:
                frac = (half_max - values[i - 1]) / denom
                left_wl = float(wavelengths[i - 1] + frac * (wavelengths[i] - wavelengths[i - 1]))
            break

    # Search right of peak for half-max crossing.
    right_wl: float | None = None
    for i in range(peak_idx, len(values) - 1):
        if values[i] >= half_max and values[i + 1] < half_max:
            denom = values[i + 1] - values[i]
            if abs(denom) < 1e-15:
                right_wl = float(wavelengths[i])
            else:
                frac = (half_max - values[i]) / denom
                right_wl = float(wavelengths[i] + frac * (wavelengths[i + 1] - wavelengths[i]))
            break

    if left_wl is None or right_wl is None:
        return 0.0

    return right_wl - left_wl


# ---------------------------------------------------------------------------
# Spectrum transformation
# ---------------------------------------------------------------------------


def translate_spectrum(
    spectrum: Spectrum,
    delta_nm: float,
    *,
    zoned: bool = True,
    zone_bounds: tuple[float, float, float, float] | None = None,
) -> Spectrum:
    """Shift a spectrum along the wavelength axis by ``delta_nm``.

    Two modes are supported:

    * **Zoned mode** (default, ``zoned=True``):  The wavelength axis is
      divided into three regions — blue (≤ 500 nm), green (500–580 nm),
      and red (> 580 nm).  Only the region containing the spectral peak
      is shifted; the other two regions are held fixed.  Gaps created
      by the shift at zone boundaries are smoothly interpolated to
      avoid discontinuities.  This preserves the blue-leakage region of
      QD spectra and prevents edge clipping at the wavelength limits.

    * **Global mode** (``zoned=False``):  The entire spectrum is shifted
      uniformly and resampled onto the original grid.  Values beyond the
      grid boundaries are clipped to zero.

    Args:
        spectrum: Input spectrum.
        delta_nm: Wavelength shift in nm. Positive = red-shift,
            negative = blue-shift.
        zoned: If True, use zone-based shifting (default).
        zone_bounds: Optional ``(blue_end, green_end, red_end,
            extra_end)`` tuple defining zone boundaries.  Defaults to
            ``(500, 580, 780, 830)``.

    Returns:
        New Spectrum with shifted values on the original wavelength grid.
    """
    if abs(delta_nm) < 1e-6:
        return Spectrum(
            wavelengths=spectrum.wavelengths.copy(),
            values=spectrum.values.copy(),
            unit=spectrum.unit,
            meta={**spectrum.meta, "translate_delta": 0.0},
        )

    if not zoned:
        # Original global-shift implementation.
        shifted_wl = spectrum.wavelengths + delta_nm
        new_values = np.interp(
            spectrum.wavelengths,
            shifted_wl,
            spectrum.values,
            left=0.0,
            right=0.0,
        )
        return Spectrum(
            wavelengths=spectrum.wavelengths.copy(),
            values=new_values,
            unit=spectrum.unit,
            meta={**spectrum.meta, "translate_delta": delta_nm},
        )

    # ---- Zoned shift ----
    return _translate_spectrum_zoned_impl(
        spectrum, delta_nm, zone_bounds,
    )


# Default zone boundaries (nm):  blue | green | red | tail
_DEFAULT_ZONE_BOUNDS: tuple[float, float, float, float] = (500.0, 580.0, 780.0, 830.0)


def _detect_peak_zone(
    spectrum: Spectrum,
    zone_bounds: tuple[float, float, float, float] | None,
) -> int:
    """Determine which zone (0=blue, 1=green, 2=red) contains the peak.

    Falls back to the zone with the largest integrated area if the peak
    sits exactly on a boundary.
    """
    bounds = zone_bounds or _DEFAULT_ZONE_BOUNDS
    wl = spectrum.wavelengths
    vals = spectrum.values
    peak_wl = float(wl[int(np.argmax(vals))])

    if peak_wl <= bounds[0]:
        return 0  # blue
    if peak_wl <= bounds[1]:
        return 1  # green
    return 2  # red


def _translate_spectrum_zoned_impl(
    spectrum: Spectrum,
    delta_nm: float,
    zone_bounds: tuple[float, float, float, float] | None,
) -> Spectrum:
    """Shift only the peak zone, preserving other zones, with boundary smoothing.

    The algorithm:
    1. Divide the spectrum into three zones by *zone_bounds*.
    2. Determine which zone contains the spectral peak.
    3. Shift only that zone's data by *delta_nm* via interpolation.
    4. For the shifted zone, fill the gap left behind (near the boundary
       with the previous zone) by holding the boundary value constant —
       i.e. the gap region takes the value of the nearest un-shifted
       boundary point, then a short smoothing window blends the
       transition.
    5. Zones that do not contain the peak are kept unchanged.
    """
    bounds = zone_bounds or _DEFAULT_ZONE_BOUNDS
    wl = spectrum.wavelengths.copy()
    vals = spectrum.values.copy()
    n = len(wl)
    dwl = float(wl[1] - wl[0]) if n > 1 else 1.0

    # Zone masks
    blue_mask = wl <= bounds[0]
    green_mask = (wl > bounds[0]) & (wl <= bounds[1])
    red_mask = wl > bounds[1]

    # Also define mask for the shifted zone
    peak_zone = _detect_peak_zone(spectrum, zone_bounds)
    if peak_zone == 0:
        shift_mask = blue_mask
    elif peak_zone == 1:
        shift_mask = green_mask
    else:
        shift_mask = red_mask

    if not np.any(shift_mask):
        return Spectrum(
            wavelengths=wl, values=vals, unit=spectrum.unit,
            meta={**spectrum.meta, "translate_delta": delta_nm, "zoned": True},
        )

    # --- Shift the peak zone ---
    zone_wl = wl[shift_mask]
    zone_vals = vals[shift_mask]
    shifted_wl = zone_wl + delta_nm

    # Interpolate shifted zone data back onto the zone's original grid
    shifted_zone_vals = np.interp(
        zone_wl, shifted_wl, zone_vals,
        left=0.0, right=0.0,
    )

    # --- Handle the gap at the boundary ---
    # After shifting, a gap appears at the edge of the shifted zone
    # closest to the previous zone. We fill this gap with the boundary
    # value from the un-shifted neighbour, then apply smoothing.
    new_vals = vals.copy()
    new_vals[shift_mask] = shifted_zone_vals

    # Determine which boundary of the shifted zone has a gap
    zone_indices = np.where(shift_mask)[0]
    zone_start = zone_indices[0]
    zone_end = zone_indices[-1]

    # Smoothing window (in nm) for boundary blending
    smooth_nm = max(abs(delta_nm) * 2, 10.0)
    smooth_points = max(int(round(smooth_nm / dwl)), 3)

    if delta_nm > 0:
        # Red-shift: gap appears at the LEFT (low-wavelength) edge of the zone.
        # The shifted data starts further right, leaving a gap near zone_start.
        if zone_start > 0:
            boundary_val = float(vals[zone_start - 1])  # value from previous zone
            gap_end = min(zone_start + int(round(abs(delta_nm) / dwl)), zone_end)
            if gap_end > zone_start:
                # Fill gap with boundary value
                new_vals[zone_start:gap_end + 1] = boundary_val
                # Smooth only within the shifted zone (do not touch the
                # previous zone's data).
                smooth_start = zone_start + 1
                smooth_end = min(gap_end + smooth_points, zone_end)
                _smooth_segment(new_vals, smooth_start, smooth_end)
    else:
        # Blue-shift: gap appears at the RIGHT (high-wavelength) edge.
        if zone_end < n - 1:
            boundary_val = float(vals[zone_end + 1])  # value from next zone
            gap_start = max(zone_end - int(round(abs(delta_nm) / dwl)), zone_start)
            if zone_end > gap_start:
                # Fill gap with boundary value
                new_vals[gap_start:zone_end + 1] = boundary_val
                # Smooth only within the shifted zone.
                smooth_start = max(gap_start - smooth_points, zone_start)
                smooth_end = zone_end - 1
                _smooth_segment(new_vals, smooth_start, smooth_end)

    # Ensure non-negative
    new_vals = np.clip(new_vals, 0.0, None)

    return Spectrum(
        wavelengths=wl,
        values=new_vals,
        unit=spectrum.unit,
        meta={
            **spectrum.meta,
            "translate_delta": delta_nm,
            "zoned": True,
            "peak_zone": peak_zone,
        },
    )


def _smooth_segment(arr: np.ndarray, start: int, end: int) -> None:
    """Apply a simple moving-average smooth to ``arr[start:end+1]`` in place."""
    if end - start < 2:
        return
    segment = arr[start:end + 1].copy()
    window = min(5, len(segment))
    if window < 2:
        return
    kernel = np.ones(window) / window
    smoothed = np.convolve(segment, kernel, mode='same')
    # Fix edges of 'same' convolution
    half = window // 2
    smoothed[:half] = segment[:half]
    smoothed[-half:] = segment[-half:]
    arr[start:end + 1] = smoothed


def scale_fwhm(
    spectrum: Spectrum,
    factor: float,
) -> Spectrum:
    """Scale the FWHM of a spectrum by resampling around the peak.

    This method works for arbitrary line shapes (Gaussian, Lorentzian,
    asymmetric peaks) by stretching the wavelength axis around the peak
    and resampling onto the original grid.  This is more robust than the
    previous power-transformation approach, which was only exact for
    Gaussian peaks and produced >100% FWHM errors for Lorentzian lines.

    Args:
        spectrum: Input spectrum.
        factor: FWHM scaling factor (1.0 = no change, 2.0 = double FWHM,
            0.5 = halve FWHM).

    Returns:
        New Spectrum with scaled FWHM.

    Raises:
        ValueError: If factor <= 0.
    """
    if factor <= 0:
        raise ValueError(f"FWHM scaling factor must be positive, got {factor}")
    if abs(factor - 1.0) < 1e-6:
        return Spectrum(
            wavelengths=spectrum.wavelengths.copy(),
            values=spectrum.values.copy(),
            unit=spectrum.unit,
            meta={**spectrum.meta, "fwhm_factor": 1.0},
        )

    vals = np.asarray(spectrum.values, dtype=np.float64)
    # Clean NaN/Inf to prevent silent propagation.
    if np.any(~np.isfinite(vals)):
        vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)

    peak_val = float(np.max(vals))
    if peak_val <= 0:
        return Spectrum(
            wavelengths=spectrum.wavelengths.copy(),
            values=spectrum.values.copy(),
            unit=spectrum.unit,
            meta={**spectrum.meta, "fwhm_factor": factor},
        )

    peak_idx = int(np.argmax(vals))
    peak_wl = float(spectrum.wavelengths[peak_idx])

    # Stretch the wavelength axis around the peak by *factor*, then
    # resample back onto the original grid.  This preserves the peak
    # position and amplitude while scaling the width of any feature.
    scaled_wl = peak_wl + (spectrum.wavelengths - peak_wl) * factor
    new_values = np.interp(
        spectrum.wavelengths, scaled_wl, vals, left=0.0, right=0.0,
    )

    return Spectrum(
        wavelengths=spectrum.wavelengths.copy(),
        values=new_values,
        unit=spectrum.unit,
        meta={**spectrum.meta, "fwhm_factor": factor},
    )


# ---------------------------------------------------------------------------
# QD blue-leakage handling
# ---------------------------------------------------------------------------


def compute_leakage_ratio(
    qd_spectrum: Spectrum,
    b_led_spectrum: Spectrum,
    blue_cutoff: float = 500.0,
) -> float:
    """Compute the blue leakage ratio *k* from a QD spectrum.

    In the blue region (λ < ``blue_cutoff``), the QD spectrum is assumed
    to be entirely blue leakage: QD(λ) ≈ k × B_LED(λ).  The ratio *k*
    is estimated by least-squares fitting:

        k = Σ(QD × B_LED) / Σ(B_LED²)    in the blue region

    Args:
        qd_spectrum: The combined QD spectrum (blue leakage + QD emission).
        b_led_spectrum: The B-LED source spectrum.
        blue_cutoff: Wavelength below which is considered pure blue leakage.

    Returns:
        Leakage ratio *k* (dimensionless). Returns 0.0 if no valid data
        exists in the blue region.
    """
    # Interpolate B-LED onto QD wavelength grid.
    b_led_vals = np.interp(
        qd_spectrum.wavelengths,
        b_led_spectrum.wavelengths,
        b_led_spectrum.values,
        left=0.0,
        right=0.0,
    )

    # Select blue region where B-LED has meaningful signal.
    mask = (qd_spectrum.wavelengths < blue_cutoff) & (b_led_vals > 1e-10)

    if not np.any(mask):
        return 0.0

    qd_blue = qd_spectrum.values[mask]
    b_blue = b_led_vals[mask]

    # Least-squares: k = sum(qd * b) / sum(b * b)
    denom = float(np.sum(b_blue * b_blue))
    if denom < 1e-20:
        return 0.0

    return max(0.0, float(np.sum(qd_blue * b_blue) / denom))


def separate_qd_spectrum(
    qd_spectrum: Spectrum,
    b_led_spectrum: Spectrum,
    blue_cutoff: float = 500.0,
) -> tuple[Spectrum, Spectrum]:
    """Separate a QD spectrum into blue leakage and QD emission components.

    The blue leakage is modelled as *k × B_LED(λ)*, where *k* is
    estimated by least-squares fitting in the blue region
    (λ < ``blue_cutoff``).  The QD emission is the residual:
    QD_total − blue_leakage, clipped to non-negative values.

    Args:
        qd_spectrum: The combined QD spectrum.
        b_led_spectrum: The B-LED source spectrum.
        blue_cutoff: Wavelength separating blue leakage from QD emission.

    Returns:
        Tuple of (blue_leakage_spectrum, qd_emission_spectrum), both on
        the same wavelength grid as ``qd_spectrum``.
    """
    k = compute_leakage_ratio(qd_spectrum, b_led_spectrum, blue_cutoff)

    # Interpolate B-LED onto QD wavelength grid.
    b_led_vals = np.interp(
        qd_spectrum.wavelengths,
        b_led_spectrum.wavelengths,
        b_led_spectrum.values,
        left=0.0,
        right=0.0,
    )

    # Blue leakage = k * B_LED.
    blue_leakage_vals = k * b_led_vals

    # QD emission = total − blue leakage (clipped to ≥ 0).
    qd_emission_vals = np.clip(qd_spectrum.values - blue_leakage_vals, 0.0, None)

    # Zero out QD emission below blue_cutoff to prevent residual values
    # in the blue region from being affected by translate/scale operations.
    # This ensures that only the QD emission peak is adjusted, while the
    # blue leakage component remains exactly preserved.
    blue_mask = qd_spectrum.wavelengths < blue_cutoff
    qd_emission_vals[blue_mask] = 0.0

    wl = qd_spectrum.wavelengths
    unit = qd_spectrum.unit

    blue_leakage = Spectrum(
        wavelengths=wl.copy(),
        values=blue_leakage_vals,
        unit=unit,
        meta={"type": "blue_leakage", "leakage_ratio": k, **qd_spectrum.meta},
    )
    qd_emission = Spectrum(
        wavelengths=wl.copy(),
        values=qd_emission_vals,
        unit=unit,
        meta={"type": "qd_emission", "leakage_ratio": k, **qd_spectrum.meta},
    )

    return blue_leakage, qd_emission


def recompose_qd_spectrum(
    blue_leakage: Spectrum,
    qd_emission: Spectrum,
    wavelengths: NDArray[np.float64] | None = None,
    unit: str = "a.u.",
) -> Spectrum:
    """Combine blue leakage and QD emission into a full QD spectrum.

    Args:
        blue_leakage: Blue leakage component spectrum.
        qd_emission: QD emission component spectrum.
        wavelengths: Optional target wavelength grid. If None, uses the
            blue_leakage grid.
        unit: Unit string for the output spectrum.

    Returns:
        Combined QD spectrum.
    """
    if wavelengths is None:
        wavelengths = blue_leakage.wavelengths
        bl_vals = blue_leakage.values
        qd_vals = qd_emission.values
        # Interpolate QD emission if grids differ.
        if not np.allclose(qd_emission.wavelengths, wavelengths):
            qd_vals = np.interp(
                wavelengths, qd_emission.wavelengths, qd_emission.values,
                left=0.0, right=0.0,
            )
    else:
        bl_vals = np.interp(
            wavelengths, blue_leakage.wavelengths, blue_leakage.values,
            left=0.0, right=0.0,
        )
        qd_vals = np.interp(
            wavelengths, qd_emission.wavelengths, qd_emission.values,
            left=0.0, right=0.0,
        )

    total_vals = bl_vals + qd_vals

    return Spectrum(
        wavelengths=np.asarray(wavelengths, dtype=np.float64),
        values=total_vals,
        unit=unit,
        meta={"type": "qd_total"},
    )


def update_qd_blue_leakage(
    qd_spectrum: Spectrum,
    old_b_led: Spectrum,
    new_b_led: Spectrum,
    blue_cutoff: float = 500.0,
) -> Spectrum:
    """Update the blue leakage in a QD spectrum when the B-LED changes.

    The leakage ratio *k* is computed from the original QD spectrum and
    the original B-LED.  The new blue leakage is *k × new_B_LED(λ)*.
    The QD emission component is preserved unchanged.

    Args:
        qd_spectrum: Original combined QD spectrum.
        old_b_led: Original B-LED spectrum (before adjustment).
        new_b_led: Adjusted B-LED spectrum.
        blue_cutoff: Wavelength separating blue leakage from QD emission.

    Returns:
        New QD spectrum with updated blue leakage and preserved QD emission.
    """
    # Separate original spectrum to extract k and QD emission.
    blue_leakage, qd_emission = separate_qd_spectrum(qd_spectrum, old_b_led, blue_cutoff)
    k = blue_leakage.meta.get("leakage_ratio", 0.0)

    # New blue leakage = k * new_B_LED on the QD wavelength grid.
    new_b_led_vals = np.interp(
        qd_spectrum.wavelengths,
        new_b_led.wavelengths,
        new_b_led.values,
        left=0.0,
        right=0.0,
    )
    new_blue_leakage_vals = k * new_b_led_vals

    # Recombine: new leakage + unchanged QD emission.
    total_vals = new_blue_leakage_vals + qd_emission.values

    return Spectrum(
        wavelengths=qd_spectrum.wavelengths.copy(),
        values=total_vals,
        unit=qd_spectrum.unit,
        meta={
            **qd_spectrum.meta,
            "blue_leakage_updated": True,
            "leakage_ratio": k,
        },
    )


def adjust_qd_emission(
    qd_spectrum: Spectrum,
    b_led_spectrum: Spectrum,
    peak_delta: float = 0.0,
    fwhm_factor: float = 1.0,
    blue_cutoff: float = 500.0,
) -> Spectrum:
    """Adjust the QD emission peak, preserving blue leakage.

    Separates the QD spectrum into blue leakage and QD emission, applies
    peak wavelength shift and FWHM scaling to the QD emission only, then
    recombines.

    Args:
        qd_spectrum: Original combined QD spectrum.
        b_led_spectrum: The B-LED source spectrum (for separation).
        peak_delta: Wavelength shift in nm for the QD emission peak.
        fwhm_factor: FWHM scaling factor for the QD emission.
        blue_cutoff: Wavelength separating blue leakage from QD emission.

    Returns:
        New QD spectrum with adjusted emission and preserved blue leakage.
    """
    blue_leakage, qd_emission = separate_qd_spectrum(
        qd_spectrum, b_led_spectrum, blue_cutoff,
    )

    # Apply transformations to QD emission only.
    adjusted = qd_emission
    if abs(peak_delta) > 1e-6:
        adjusted = translate_spectrum(adjusted, peak_delta)
    if abs(fwhm_factor - 1.0) > 1e-6:
        adjusted = scale_fwhm(adjusted, fwhm_factor)

    # Recombine with original blue leakage.
    return recompose_qd_spectrum(blue_leakage, adjusted)


def adjust_qd_full(
    qd_spectrum: Spectrum,
    old_b_led: Spectrum,
    new_b_led: Spectrum,
    peak_delta: float = 0.0,
    fwhm_factor: float = 1.0,
    blue_cutoff: float = 500.0,
) -> Spectrum:
    """Adjust both QD emission and blue leakage simultaneously.

    This handles the case where both the B-LED and the QD emission are
    being adjusted at the same time:

    1. Separate the original QD spectrum using the *original* B-LED to
       extract the leakage ratio *k* and the QD emission component.
    2. Apply peak/FWHM adjustments to the QD emission.
    3. Compute new blue leakage = *k × new_B_LED(λ)*.
    4. Recombine.

    Args:
        qd_spectrum: Original combined QD spectrum.
        old_b_led: Original B-LED spectrum (before B-LED adjustment).
        new_b_led: Adjusted B-LED spectrum (after B-LED adjustment).
        peak_delta: Wavelength shift in nm for the QD emission peak.
        fwhm_factor: FWHM scaling factor for the QD emission.
        blue_cutoff: Wavelength separating blue leakage from QD emission.

    Returns:
        New QD spectrum with both adjusted emission and updated leakage.
    """
    # Separate using original B-LED to get k and QD emission.
    blue_leakage, qd_emission = separate_qd_spectrum(
        qd_spectrum, old_b_led, blue_cutoff,
    )
    k = blue_leakage.meta.get("leakage_ratio", 0.0)

    # Adjust QD emission.
    adjusted_emission = qd_emission
    if abs(peak_delta) > 1e-6:
        adjusted_emission = translate_spectrum(adjusted_emission, peak_delta)
    if abs(fwhm_factor - 1.0) > 1e-6:
        adjusted_emission = scale_fwhm(adjusted_emission, fwhm_factor)

    # New blue leakage = k * new_B_LED on the QD wavelength grid.
    new_b_led_vals = np.interp(
        qd_spectrum.wavelengths,
        new_b_led.wavelengths,
        new_b_led.values,
        left=0.0,
        right=0.0,
    )
    new_blue_leakage_vals = k * new_b_led_vals

    # Recombine.
    total_vals = new_blue_leakage_vals + adjusted_emission.values

    return Spectrum(
        wavelengths=qd_spectrum.wavelengths.copy(),
        values=total_vals,
        unit=qd_spectrum.unit,
        meta={
            **qd_spectrum.meta,
            "emission_adjusted": True,
            "leakage_updated": True,
            "leakage_ratio": k,
            "peak_delta": peak_delta,
            "fwhm_factor": fwhm_factor,
        },
    )
