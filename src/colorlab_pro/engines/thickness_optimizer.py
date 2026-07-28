"""ThicknessOptimizer Engine.

Provides three optimization strategies for color-filter (CF) thickness:

1. **Grid search** (``grid_search_optimize``, primary):
   Exhaustive grid search over 3-channel thickness space. Each channel is
   sampled at ``steps`` points (default 10 → 1000 total combinations).
   For each combination, the filtered white spectrum and device gamut are
   computed, then results are ranked by delta-xy and coverage. This is the
   method used by the Thickness Optimizer page.

2. **Stacked-filter model** (``optimize_thickness``, legacy):
   A single source spectrum passes through a stack of filters.
       T(lambda) = prod_i 10^(-alpha_i(lambda) * d_i)
       S(lambda) = source(lambda) * T(lambda)

3. **Display model** (``optimize_thickness_display``, L-BFGS-B):
   Each primary source (R/G/B) passes through its own CF, then mixed.
       S_i(lambda) = source_i(lambda) * 10^(-alpha_i(lambda) * d_i)
       S(lambda) = sum_i S_i(lambda)
   Uses scipy.optimize.minimize (L-BFGS-B) for gradient-based optimization.

All models use Lambert-Beer law: T = 10^(-alpha * d), where alpha is the
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


# ---------------------------------------------------------------------------
# Model 3: Grid search (primary method used by the Thickness Optimizer page)
# ---------------------------------------------------------------------------

from colorlab_pro.engines.gamut_calculator import (
    build_gamut_from_primaries,
    coverage,
    match,
    standard_gamuts,
)
from colorlab_pro.engines.spectrum_analyzer import xy as spectrum_xy


def _prepare_grid_inputs(
    sources: list[Spectrum],
    cfs: list[Spectrum],
) -> tuple[NDArray[np.float64], list[NDArray[np.float64]], list[NDArray[np.float64]], str]:
    """Resample sources and CFs to a common wavelength grid, convert CF to alpha.

    Returns:
        (wavelengths, source_values_list, alpha_list, unit)
    """
    wavelengths = sources[0].wavelengths.copy()
    for s in sources[1:]:
        wavelengths = np.intersect1d(wavelengths, s.wavelengths)
    for c in cfs:
        wavelengths = np.intersect1d(wavelengths, c.wavelengths)
    if len(wavelengths) < 3:
        raise ValueError("Insufficient common wavelength points between spectra")

    def _resample(spec: Spectrum) -> NDArray[np.float64]:
        return np.interp(wavelengths, spec.wavelengths, spec.values)

    src_vals = [_resample(s) for s in sources]
    cf_vals = [_resample(c) for c in cfs]

    def _transmittance_to_alpha(t: NDArray[np.float64]) -> NDArray[np.float64]:
        t = np.asarray(t, dtype=float)
        if np.max(t) > 1.5:
            t = t / 100.0
        t = np.clip(t, 1e-6, 1.0)
        return -np.log10(t)

    alphas = [_transmittance_to_alpha(v) for v in cf_vals]
    return wavelengths, src_vals, alphas, sources[0].unit


def _compute_single_candidate(
    wavelengths: NDArray[np.float64],
    src_vals: list[NDArray[np.float64]],
    alphas: list[NDArray[np.float64]],
    thicknesses: list[float],
    target: XY,
    target_gamut: Any,
    unit: str,
) -> dict:
    """Compute filtered spectra, white xy, delta, coverage, match for one thickness combo."""
    filtered = []
    for src, alpha, d in zip(src_vals, alphas, thicknesses, strict=False):
        t = np.power(10.0, -alpha * d)
        filtered.append(src * t)
    white_spec = Spectrum(wavelengths=wavelengths, values=sum(filtered), unit=unit)
    white_xy = spectrum_xy(white_spec)
    delta = float(np.hypot(white_xy.x - target.x, white_xy.y - target.y))

    primaries_xy = [
        spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=unit))
        for v in filtered
    ]
    device = build_gamut_from_primaries(
        "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
    )
    cov = coverage(target_gamut, device)
    m = match(target_gamut, device)
    return {
        "thickness_r": round(float(thicknesses[0]), 3),
        "thickness_g": round(float(thicknesses[1]), 3),
        "thickness_b": round(float(thicknesses[2]), 3),
        "white_xy": [round(white_xy.x, 4), round(white_xy.y, 4)],
        "delta_xy": round(delta, 4),
        "coverage": round(cov, 1),
        "match": round(m, 1),
    }


def grid_search_optimize(
    sources: list[Spectrum],
    cfs: list[Spectrum],
    bounds: list[tuple[float, float]],
    target_xy: XY,
    target_standard: str = "BT2020",
    steps: int = 10,
    *,
    progress_callback: Callable[[int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict]:
    """Grid-search thickness optimization for 3-channel display model.

    Samples each channel at ``steps`` points within the given bounds,
    computes the device gamut and white point for each combination,
    and returns results ranked by delta-xy (ascending) then coverage
    (descending).

    Args:
        sources: Primary source spectra [R, G, B].
        cfs: Color filter (absorber) spectra [RCF, GCF, BCF].
        bounds: Per-channel (min, max) thickness bounds in μm.
        target_xy: Target white-point chromaticity.
        target_standard: Gamut standard name for coverage/match (default "BT2020").
        steps: Grid resolution per channel (default 10 → 1000 combos).
        progress_callback: Invoked with 0-100 percent during search.
        cancel_check: If returns True, search is aborted early.

    Returns:
        List of result dicts, sorted by (delta_xy, -coverage), limited to top 5.
        Each dict has keys: thickness_r/g/b, white_xy, delta_xy, coverage, match, rank.
    """
    target_gamut = standard_gamuts(target_standard)
    wavelengths, src_vals, alphas, unit = _prepare_grid_inputs(sources, cfs)

    total = steps ** 3
    candidates: list[dict] = []
    count = 0

    for dr in np.linspace(bounds[0][0], bounds[0][1], steps):
        for dg in np.linspace(bounds[1][0], bounds[1][1], steps):
            for db in np.linspace(bounds[2][0], bounds[2][1], steps):
                count += 1
                if cancel_check and cancel_check():
                    return []
                if progress_callback and count % 50 == 0:
                    progress_callback(int(100 * count / total))
                candidates.append(
                    _compute_single_candidate(
                        wavelengths, src_vals, alphas,
                        [dr, dg, db], target_xy, target_gamut, unit,
                    )
                )

    candidates.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
    top = candidates[:5]
    for i, r in enumerate(top):
        r["rank"] = i + 1
    return top


def sensitivity_analysis(
    sources: list[Spectrum],
    cfs: list[Spectrum],
    bounds: list[tuple[float, float]],
    base_thicknesses: list[float],
    vary_channel: int,
    target_xy: XY,
    target_standard: str = "BT2020",
    steps: int = 21,
    *,
    progress_callback: Callable[[int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict]:
    """Single-channel sensitivity analysis.

    Varies one channel's thickness while holding the other two fixed at
    ``base_thicknesses``, returning coverage and white-point drift.

    Args:
        sources: Primary source spectra [R, G, B].
        cfs: Color filter spectra [RCF, GCF, BCF].
        bounds: Per-channel (min, max) thickness bounds.
        base_thicknesses: Best thicknesses [R, G, B] to fix the other channels.
        vary_channel: Index of the channel to vary (0=R, 1=G, 2=B).
        target_xy: Target white point.
        target_standard: Gamut standard for coverage.
        steps: Number of sample points along the thickness range.
        progress_callback: Invoked with 0-100 percent.
        cancel_check: If returns True, aborts early.

    Returns:
        List of dicts with keys: thickness, coverage, white_x, white_y.
    """
    target_gamut = standard_gamuts(target_standard)
    wavelengths, src_vals, alphas, unit = _prepare_grid_inputs(sources, cfs)

    lo, hi = bounds[vary_channel]
    points: list[dict] = []

    for idx, d in enumerate(np.linspace(lo, hi, steps)):
        if cancel_check and cancel_check():
            break
        if progress_callback:
            progress_callback(int(100 * (idx + 1) / steps))
        ds = list(base_thicknesses)
        ds[vary_channel] = d
        filtered = []
        for src, alpha, dd in zip(src_vals, alphas, ds, strict=False):
            t = np.power(10.0, -alpha * dd)
            filtered.append(src * t)
        primaries_xy = [
            spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=unit))
            for v in filtered
        ]
        white_spec = Spectrum(wavelengths=wavelengths, values=sum(filtered), unit=unit)
        white_xy = spectrum_xy(white_spec)
        device = build_gamut_from_primaries(
            "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
        )
        cov = coverage(target_gamut, device)
        points.append({
            "thickness": round(float(d), 3),
            "coverage": round(float(cov), 1),
            "white_x": round(float(white_xy.x), 4),
            "white_y": round(float(white_xy.y), 4),
        })
    return points


def sensitivity_all_channels(
    sources: list[Spectrum],
    cfs: list[Spectrum],
    bounds: list[tuple[float, float]],
    base_thicknesses: list[float],
    target_standard: str = "BT2020",
    steps: int = 21,
    *,
    progress_callback: Callable[[int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, list[dict]]:
    """Run sensitivity analysis for all three channels.

    Returns:
        Dict mapping channel name ("R"/"G"/"B") to list of {thickness, coverage} dicts.
    """
    target_gamut = standard_gamuts(target_standard)
    wavelengths, src_vals, alphas, unit = _prepare_grid_inputs(sources, cfs)

    total = steps * 3
    count = 0
    channel_names = {0: "R", 1: "G", 2: "B"}
    results: dict[str, list[dict]] = {}

    for ch_idx in range(3):
        lo, hi = bounds[ch_idx]
        points: list[dict] = []
        for _, d in enumerate(np.linspace(lo, hi, steps)):
            if cancel_check and cancel_check():
                break
            count += 1
            if progress_callback and count % 30 == 0:
                progress_callback(int(100 * count / total))
            ds = list(base_thicknesses)
            ds[ch_idx] = d
            filtered = []
            for src, alpha, dd in zip(src_vals, alphas, ds, strict=False):
                t = np.power(10.0, -alpha * dd)
                filtered.append(src * t)
            primaries_xy = [
                spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=unit))
                for v in filtered
            ]
            white_spec = Spectrum(wavelengths=wavelengths, values=sum(filtered), unit=unit)
            white_xy = spectrum_xy(white_spec)
            device = build_gamut_from_primaries(
                "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
            )
            cov = coverage(target_gamut, device)
            points.append({
                "thickness": round(float(d), 3),
                "coverage": round(float(cov), 1),
            })
        results[channel_names[ch_idx]] = points

    return results
