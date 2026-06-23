"""ThicknessOptimizer Engine.

Provides two physical models for color-filter (CF) thickness optimization:

1. **Stacked-filter model** (legacy, ``optimize_thickness``):
   A single source spectrum passes through a stack of filters.
       T(lambda) = prod_i 10^(-alpha_i(lambda) * d_i)
       S(lambda) = source(lambda) * T(lambda)
   Suitable for a single light path with cascaded filters.

2. **Display model** (``optimize_thickness_display``):
   Each primary source (R/G/B) passes through its own CF, then the three
   filtered spectra are mixed (summed) to form the white spectrum.
       S_i(lambda) = source_i(lambda) * 10^(-alpha_i(lambda) * d_i)
       S(lambda) = sum_i S_i(lambda)
   This matches the physical light path of an RGB display where each
   emission channel has its own color filter.

Both models use Lambert-Beer law: T = 10^(-alpha * d), where alpha is the
absorption coefficient (1/um) derived from CF transmittance via
alpha = -log10(T).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from colorlab_pro.dto.color import XY, OptimizationResult
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.spectrum_analyzer import xy

CF_THICKNESS_BOUNDS_UM = (0.1, 10.0)


class OptimizationCancelledError(Exception):
    """Raised when the user cancels the optimization via ``cancel_callback``."""


def _combined_transmission(
    wavelengths: NDArray[np.float64],
    alphas: list[NDArray[np.float64]],
    thicknesses: list[float],
) -> NDArray[np.float64]:
    """Compute combined (stacked) transmission for given alphas and thicknesses."""
    t = np.ones_like(wavelengths)
    for alpha, d in zip(alphas, thicknesses, strict=True):
        t = t * np.power(10.0, -alpha * d)
    return t


def _single_channel_transmission(
    alpha: NDArray[np.float64],
    thickness: float,
) -> NDArray[np.float64]:
    """Compute transmission for a single filter channel."""
    return np.power(10.0, -alpha * thickness)


def _align_alpha(
    wavelengths: NDArray[np.float64],
    absorber: Spectrum,
) -> NDArray[np.float64]:
    """Align an absorber spectrum to the target wavelength grid."""
    if (
        absorber.wavelengths.shape == wavelengths.shape
        and np.allclose(absorber.wavelengths, wavelengths)
    ):
        return absorber.values.copy()
    return np.interp(wavelengths, absorber.wavelengths, absorber.values)


# ---------------------------------------------------------------------------
# Model 1: Stacked-filter (legacy)
# ---------------------------------------------------------------------------


def optimize_thickness(
    target_xy: XY,
    source_spectrum: Spectrum,
    absorbers: list[Spectrum],
    bounds_um: tuple[float, float] = CF_THICKNESS_BOUNDS_UM,
) -> OptimizationResult:
    """Optimize CF thicknesses (stacked-filter model) to match a target xy.

    The source spectrum passes through a *stack* of all filters; the product
    of transmissions is applied to the single source.

    Args:
        target_xy: Desired chromaticity.
        source_spectrum: Source spectrum before the color filter stack.
        absorbers: List of absorption coefficient spectra alpha(lambda).
        bounds_um: (min, max) thickness in micrometers. Default (0.1, 10.0).

    Returns:
        OptimizationResult with thicknesses, achieved xy, delta_xy, etc.
    """
    if len(absorbers) < 2:
        raise ValueError("Need at least two absorber channels")

    wavelengths = source_spectrum.wavelengths
    alphas = [_align_alpha(wavelengths, a) for a in absorbers]

    def objective(d: NDArray[np.float64]) -> float:
        t = _combined_transmission(wavelengths, alphas, list(d))
        s = Spectrum(
            wavelengths=wavelengths,
            values=source_spectrum.values * t,
            unit=source_spectrum.unit,
        )
        c = xy(s)
        return float(np.hypot(c.x - target_xy.x, c.y - target_xy.y))

    n = len(absorbers)
    x0 = np.full(n, 1.5, dtype=np.float64)
    opt_bounds = [bounds_um] * n

    res = minimize(
        objective,
        x0,
        method="L-BFGS-B",
        bounds=opt_bounds,
        options={"ftol": 1e-9, "gtol": 1e-6, "maxiter": 500},
    )

    d_opt = res.x
    achieved_xy = _xy_for_thicknesses(wavelengths, alphas, source_spectrum, d_opt)
    delta_xy = float(np.hypot(achieved_xy.x - target_xy.x, achieved_xy.y - target_xy.y))

    return OptimizationResult(
        thicknesses_um=tuple(float(d) for d in d_opt),
        achieved_xy=achieved_xy,
        target_xy=target_xy,
        delta_xy=delta_xy,
        converged=res.success,
        iterations=int(res.nit),
        meta={"message": str(res.message), "model": "stacked"},
    )


def _xy_for_thicknesses(
    wavelengths: NDArray[np.float64],
    alphas: list[NDArray[np.float64]],
    source_spectrum: Spectrum,
    thicknesses: NDArray[np.float64],
) -> XY:
    """Compute xy for the stacked-filter model at given thicknesses."""
    t = _combined_transmission(wavelengths, alphas, list(thicknesses))
    s = Spectrum(
        wavelengths=wavelengths,
        values=source_spectrum.values * t,
        unit=source_spectrum.unit,
    )
    return xy(s)


# ---------------------------------------------------------------------------
# Model 2: Display (per-channel filter, then mix)
# ---------------------------------------------------------------------------


def _display_white_spectrum(
    wavelengths: NDArray[np.float64],
    sources: list[NDArray[np.float64]],
    alphas: list[NDArray[np.float64]],
    thicknesses: list[float],
) -> NDArray[np.float64]:
    """Compute the mixed white spectrum for the display model.

    Each source_i is filtered by its own CF_i, then the filtered spectra are
    summed to produce the white spectrum.

    Args:
        wavelengths: Common wavelength grid.
        sources: List of source intensity arrays (one per channel).
        alphas: List of absorption coefficient arrays (one per channel).
        thicknesses: List of thickness values (one per channel).

    Returns:
        Mixed white spectrum intensity array.
    """
    white = np.zeros_like(wavelengths)
    for src, alpha, d in zip(sources, alphas, thicknesses, strict=True):
        t = _single_channel_transmission(alpha, d)
        white = white + src * t
    return white


def _display_xy_for_thicknesses(
    wavelengths: NDArray[np.float64],
    sources: list[NDArray[np.float64]],
    alphas: list[NDArray[np.float64]],
    thicknesses: NDArray[np.float64],
    unit: str,
) -> XY:
    """Compute xy for the display model at given thicknesses."""
    white_values = _display_white_spectrum(
        wavelengths, sources, alphas, list(thicknesses)
    )
    s = Spectrum(wavelengths=wavelengths, values=white_values, unit=unit)
    return xy(s)


def optimize_thickness_display(
    target_xy: XY,
    source_spectra: list[Spectrum],
    absorbers: list[Spectrum],
    bounds_um: list[tuple[float, float]] | None = None,
    *,
    cancel_callback: Callable[[np.ndarray], None] | None = None,
) -> OptimizationResult:
    """Optimize CF thicknesses (display model) to match a target white point.

    Each primary source (R/G/B) passes through its own CF, then the filtered
    spectra are summed to form the white spectrum. The optimizer minimizes
    the delta-xy between the mixed white point and ``target_xy``.

    This is the physically correct model for an RGB display where each
    emission channel has its own color filter.

    Args:
        target_xy: Desired white-point chromaticity.
        source_spectra: List of primary source spectra [R, G, B].
        absorbers: List of absorption coefficient spectra [RCF, GCF, BCF],
            one per source channel.
        bounds_um: Optional list of (min, max) bounds per channel. If None,
            ``CF_THICKNESS_BOUNDS_UM`` is used for all channels.
        cancel_callback: Optional callable invoked after each optimizer
            iteration with the current parameter vector. If it raises an
            exception, the optimization is aborted immediately.

    Returns:
        OptimizationResult with per-channel thicknesses, achieved white xy,
        delta_xy, convergence flag, and iteration count.

    Raises:
        ValueError: If the number of sources and absorbers differ, or fewer
            than two channels are provided.
        OptimizationCancelledError: If ``cancel_callback`` raises this exception.
    """
    if len(source_spectra) != len(absorbers):
        raise ValueError(
            f"Number of sources ({len(source_spectra)}) must match number of "
            f"absorbers ({len(absorbers)})"
        )
    if len(source_spectra) < 2:
        raise ValueError("Need at least two source/absorber channel pairs")

    n = len(source_spectra)
    # Use the first source's wavelength grid as the reference.
    wavelengths = source_spectra[0].wavelengths
    unit = source_spectra[0].unit

    # Align all sources and absorbers to the common wavelength grid.
    sources: list[NDArray[np.float64]] = []
    for src in source_spectra:
        if (
            src.wavelengths.shape == wavelengths.shape
            and np.allclose(src.wavelengths, wavelengths)
        ):
            sources.append(src.values.copy())
        else:
            sources.append(np.interp(wavelengths, src.wavelengths, src.values))

    alphas: list[NDArray[np.float64]] = [
        _align_alpha(wavelengths, a) for a in absorbers
    ]

    if bounds_um is None:
        bounds_um = [CF_THICKNESS_BOUNDS_UM] * n
    elif len(bounds_um) != n:
        raise ValueError(
            f"Number of bounds ({len(bounds_um)}) must match number of "
            f"channels ({n})"
        )

    def objective(d: NDArray[np.float64]) -> float:
        c = _display_xy_for_thicknesses(wavelengths, sources, alphas, d, unit)
        return float(np.hypot(c.x - target_xy.x, c.y - target_xy.y))

    x0 = np.full(n, 1.5, dtype=np.float64)
    # Clamp initial guess within bounds.
    x0 = np.clip(
        x0,
        [b[0] for b in bounds_um],
        [b[1] for b in bounds_um],
    )

    res = minimize(
        objective,
        x0,
        method="L-BFGS-B",
        bounds=bounds_um,
        callback=cancel_callback,
        options={"ftol": 1e-9, "gtol": 1e-6, "maxiter": 500},
    )

    d_opt = res.x
    achieved_xy = _display_xy_for_thicknesses(
        wavelengths, sources, alphas, d_opt, unit
    )
    delta_xy = float(
        np.hypot(achieved_xy.x - target_xy.x, achieved_xy.y - target_xy.y)
    )

    return OptimizationResult(
        thicknesses_um=tuple(float(d) for d in d_opt),
        achieved_xy=achieved_xy,
        target_xy=target_xy,
        delta_xy=delta_xy,
        converged=res.success,
        iterations=int(res.nit),
        meta={"message": str(res.message), "model": "display"},
    )


def display_transmission_for_thicknesses(
    source_spectra: list[Spectrum],
    absorbers: list[Spectrum],
    thicknesses_um: tuple[float, ...],
) -> list[Spectrum]:
    """Compute per-channel filtered spectra for the display model.

    Args:
        source_spectra: List of primary source spectra [R, G, B].
        absorbers: List of absorption coefficient spectra [RCF, GCF, BCF].
        thicknesses_um: Per-channel thickness values.

    Returns:
        List of filtered spectra (one per channel).
    """
    if len(source_spectra) != len(absorbers):
        raise ValueError("Source and absorber counts must match")
    if len(source_spectra) != len(thicknesses_um):
        raise ValueError("Source and thickness counts must match")

    wavelengths = source_spectra[0].wavelengths
    results: list[Spectrum] = []
    for src, absorber, d in zip(
        source_spectra, absorbers, thicknesses_um, strict=True
    ):
        alpha = _align_alpha(wavelengths, absorber)
        if (
            src.wavelengths.shape == wavelengths.shape
            and np.allclose(src.wavelengths, wavelengths)
        ):
            src_vals = src.values.copy()
        else:
            src_vals = np.interp(wavelengths, src.wavelengths, src.values)
        t = _single_channel_transmission(alpha, d)
        results.append(
            Spectrum(
                wavelengths=wavelengths.copy(),
                values=src_vals * t,
                unit=src.unit,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Legacy helper (kept for backward compatibility)
# ---------------------------------------------------------------------------


def transmission_for_thicknesses(
    source_spectrum: Spectrum,
    absorbers: list[Spectrum],
    thicknesses_um: tuple[float, ...],
) -> Spectrum:
    """Compute the transmitted spectrum (stacked-filter model).

    Args:
        source_spectrum: Source spectrum.
        absorbers: List of absorber spectra.
        thicknesses_um: Thickness values.

    Returns:
        Transmitted spectrum.
    """
    wavelengths = source_spectrum.wavelengths
    alphas = [_align_alpha(wavelengths, a) for a in absorbers]
    t = _combined_transmission(wavelengths, alphas, list(thicknesses_um))
    return Spectrum(
        wavelengths=wavelengths,
        values=source_spectrum.values * t,
        unit=source_spectrum.unit,
    )
