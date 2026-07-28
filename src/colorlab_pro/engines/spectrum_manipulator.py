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
) -> Spectrum:
    """Shift a spectrum along the wavelength axis by ``delta_nm``.

    The output spectrum is resampled onto the original wavelength grid.
    Values shifted beyond the grid boundaries are clipped to zero.

    Args:
        spectrum: Input spectrum.
        delta_nm: Wavelength shift in nm. Positive = red-shift,
            negative = blue-shift.

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

    # Shifted wavelengths: each original value now sits at wl + delta.
    shifted_wl = spectrum.wavelengths + delta_nm

    # Resample: interpolate original (shifted_wl, values) onto original grid.
    new_values = np.interp(
        spectrum.wavelengths,  # target grid (original)
        shifted_wl,  # source grid (shifted)
        spectrum.values,  # source values
        left=0.0,
        right=0.0,
    )

    return Spectrum(
        wavelengths=spectrum.wavelengths.copy(),
        values=new_values,
        unit=spectrum.unit,
        meta={**spectrum.meta, "translate_delta": delta_nm},
    )


def scale_fwhm(
    spectrum: Spectrum,
    factor: float,
) -> Spectrum:
    """Scale the FWHM of a spectrum by a power transformation.

    For a Gaussian peak, raising normalised values (peak = 1) to power
    *p* changes the FWHM by a factor of 1/√p.  To achieve a target FWHM
    scaling factor *f* (f > 1 → wider, f < 1 → narrower), we use
    *p* = 1/f².

    The spectrum is normalised to peak = 1 before the power operation,
    then scaled back to the original peak value.

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

    peak_val = float(np.max(spectrum.values))
    if peak_val <= 0:
        return Spectrum(
            wavelengths=spectrum.wavelengths.copy(),
            values=spectrum.values.copy(),
            unit=spectrum.unit,
            meta={**spectrum.meta, "fwhm_factor": factor},
        )

    # Normalise to [0, 1], apply power, scale back.
    norm_vals = spectrum.values / peak_val
    p = 1.0 / (factor ** 2)
    scaled_vals = np.power(np.clip(norm_vals, 0.0, 1.0), p)
    new_values = scaled_vals * peak_val

    return Spectrum(
        wavelengths=spectrum.wavelengths.copy(),
        values=new_values,
        unit=spectrum.unit,
        meta={**spectrum.meta, "fwhm_factor": factor, "power_exponent": p},
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
