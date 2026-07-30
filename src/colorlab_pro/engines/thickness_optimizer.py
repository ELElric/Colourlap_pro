"""ThicknessOptimizer Engine.

Provides optimization strategies for color-filter (CF) thickness and
emission spectrum adjustment:

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

4. **CF material selection** (``select_cf_materials``):
   Given emission spectra and fixed thickness, enumerate all CF material
   combinations from a library to find the best match for a target gamut.

5. **Emission spectrum optimization** (``optimize_emission_spectra``):
   Adjust R/G/B emission spectra (peak wavelength shift + FWHM scaling)
   to maximise target gamut coverage.  QD-R and QD-G spectra have special
   blue-leakage handling: only the QD emission peak is adjusted while the
   blue leakage is preserved, unless the B-LED spectrum is also being
   adjusted, in which case the leakage is updated proportionally.

All models use Lambert-Beer law: T = 10^(-alpha * d), where alpha is the
absorption coefficient (1/um) derived from CF transmittance via
alpha = -log10(T).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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


def _transmittance_to_alpha(
    t: NDArray[np.float64],
    meta: dict | None = None,
    reference_thickness_um: float = 1.0,
) -> NDArray[np.float64]:
    """Convert CF transmittance to absorption coefficient alpha.

    Uses Lambert-Beer law: T = 10^(-alpha * d), so
    alpha = -log10(T_ref) / d_ref where T_ref is the measured transmittance
    at reference thickness d_ref.

    Handles both 0-1 and 0-100 (percentage) scales.  The scale is
    detected via an explicit ``transmittance_unit`` meta key, or by
    heuristic (any value > 1.5 → percentage).

    Args:
        t: Transmittance values (0-1 or 0-100 scale).
        meta: Optional spectrum metadata for format hints and reference thickness.
            If ``reference_thickness_um`` key is present in meta, it overrides
            the ``reference_thickness_um`` parameter.
        reference_thickness_um: Thickness (in μm) at which *t* was measured.
            Defaults to 1.0 μm (i.e. alpha = -log10(T)).

    Returns:
        Absorption coefficient alpha = -log10(T) / d_ref where T is clipped
        to [1e-6, 1].

    Raises:
        ValueError: If reference_thickness_um <= 0.
    """
    # Allow meta to override the reference thickness parameter.
    if meta and "reference_thickness_um" in meta:
        d_ref = float(meta["reference_thickness_um"])
    else:
        d_ref = float(reference_thickness_um)
    if d_ref <= 0:
        raise ValueError(f"reference_thickness_um must be positive, got {d_ref}")

    t = np.asarray(t, dtype=float)
    # Clean NaN/Inf to prevent silent propagation.
    if np.any(~np.isfinite(t)):
        t = np.nan_to_num(t, nan=0.0, posinf=0.0, neginf=0.0)

    is_percent = False
    if meta and meta.get("transmittance_unit", "").lower() in ("percent", "%", "0-100"):
        is_percent = True
    # Only use the simple > 1.5 heuristic; the previous ratio-based heuristic
    # (max/min > 100 && max > 0.15) incorrectly classified high-contrast 0-1
    # spectra as percentage-scale.
    if not is_percent and np.max(t) > 1.5:
        is_percent = True
    if is_percent:
        t = t / 100.0
    t = np.clip(t, 1e-6, 1.0)
    return -np.log10(t) / d_ref


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
            NOTE: these must be absorption coefficients, *not* CF transmittance.
            ``grid_search_optimize`` consumes transmittance and converts it
            internally via ``_transmittance_to_alpha``; this legacy stacked-
            filter model consumes alpha directly. Use ``_transmittance_to_alpha``
            to convert measured CF transmittance to alpha.
        bounds_um: (min, max) thickness in micrometers. Default (0.1, 10.0).

    Returns:
        OptimizationResult with thicknesses, achieved xy, delta_xy, etc.
    """
    # API note: ``absorbers`` are absorption coefficient alpha(lambda) arrays,
    # not CF transmittance (cf. grid_search_optimize which expects transmittance).
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
        absorbers: List of absorption coefficient spectra alpha(lambda)
            [RCF, GCF, BCF], one per source channel. NOTE: these must be
            absorption coefficients, *not* CF transmittance.
            ``grid_search_optimize`` consumes transmittance and converts it
            internally via ``_transmittance_to_alpha``; this display model
            consumes alpha directly. Use ``_transmittance_to_alpha`` to
            convert measured CF transmittance to alpha.
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
    # API note: ``absorbers`` are absorption coefficient alpha(lambda) arrays,
    # not CF transmittance (cf. grid_search_optimize which expects transmittance).
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

    Uses ``np.intersect1d`` on wavelengths rounded to 1 decimal place to avoid
    floating-point mismatches (e.g. 450.0 vs 450.0000001).

    Returns:
        (wavelengths, source_values_list, alpha_list, unit)
    """
    # Round to 1 decimal place for robust intersection.
    wavelengths = np.round(sources[0].wavelengths, 1)
    for s in sources[1:]:
        wavelengths = np.intersect1d(wavelengths, np.round(s.wavelengths, 1))
    for c in cfs:
        wavelengths = np.intersect1d(wavelengths, np.round(c.wavelengths, 1))
    if len(wavelengths) < 3:
        raise ValueError("Insufficient common wavelength points between spectra")

    def _resample(spec: Spectrum) -> NDArray[np.float64]:
        return np.interp(wavelengths, spec.wavelengths, spec.values)

    src_vals = [_resample(s) for s in sources]
    cf_vals = [_resample(c) for c in cfs]

    alphas = [_transmittance_to_alpha(v, c.meta) for v, c in zip(cf_vals, cfs, strict=True)]
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
    """Compute filtered spectra, white xy, delta, coverage, match for one thickness combo.

    Returns full-precision floats (not rounded) so callers can sort by exact
    values.  Frontend code formats display precision via ``toFixed()``.

    If the total filtered intensity is near zero (e.g. all CFs very thick),
    returns sentinel values (delta_xy=inf, coverage=0, match=0) to prevent
    NaN propagation through ``spectrum_xy`` and downstream sorting.
    """
    filtered = []
    for src, alpha, d in zip(src_vals, alphas, thicknesses, strict=True):
        t = np.power(10.0, -alpha * d)
        filtered.append(src * t)
    white_vals = np.sum(np.stack(filtered), axis=0)

    # Guard against zero / near-zero total intensity — spectrum_xy would
    # produce NaN because XYZ = (0, 0, 0) and normalisation divides by zero.
    total_intensity = float(np.sum(white_vals))
    if total_intensity < 1e-12:
        return {
            "thickness_r": float(thicknesses[0]),
            "thickness_g": float(thicknesses[1]),
            "thickness_b": float(thicknesses[2]),
            "white_xy": [float("nan"), float("nan")],
            "delta_xy": float("inf"),
            "coverage": 0.0,
            "match": 0.0,
        }

    white_spec = Spectrum(wavelengths=wavelengths, values=white_vals, unit=unit)
    white_xy = spectrum_xy(white_spec)

    # Guard against NaN from colour-science (can happen for edge-case spectra).
    if np.isnan(white_xy.x) or np.isnan(white_xy.y):
        return {
            "thickness_r": float(thicknesses[0]),
            "thickness_g": float(thicknesses[1]),
            "thickness_b": float(thicknesses[2]),
            "white_xy": [float("nan"), float("nan")],
            "delta_xy": float("inf"),
            "coverage": 0.0,
            "match": 0.0,
        }

    delta = float(np.hypot(white_xy.x - target.x, white_xy.y - target.y))

    primaries_xy = [
        spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=unit))
        for v in filtered
    ]

    # Guard against NaN in any primary channel (e.g. one CF is so thick that
    # the filtered spectrum is effectively zero).  Build a valid gamut only
    # when all three primaries have finite xy.
    if any(np.isnan(p.x) or np.isnan(p.y) for p in primaries_xy):
        return {
            "thickness_r": float(thicknesses[0]),
            "thickness_g": float(thicknesses[1]),
            "thickness_b": float(thicknesses[2]),
            "white_xy": [float(white_xy.x), float(white_xy.y)],
            "delta_xy": delta,
            "coverage": 0.0,
            "match": 0.0,
        }

    device = build_gamut_from_primaries(
        "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
    )
    cov = coverage(target_gamut, device)
    m = match(target_gamut, device)
    return {
        "thickness_r": float(thicknesses[0]),
        "thickness_g": float(thicknesses[1]),
        "thickness_b": float(thicknesses[2]),
        "white_xy": [float(white_xy.x), float(white_xy.y)],
        "delta_xy": delta,
        "coverage": float(cov),
        "match": float(m),
    }


def grid_search_optimize(
    sources: list[Spectrum],
    cfs: list[Spectrum],
    bounds: list[tuple[float, float]],
    target_xy: XY,
    target_standard: str = "BT2020",
    steps: int = 10,
    *,
    sort_by: str = "match",
    delta_threshold: float = 0.02,
    progress_callback: Callable[[int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict]:
    """Grid-search thickness optimization for 3-channel display model.

    Samples each channel at ``steps`` points within the given bounds,
    computes the device gamut and white point for each combination,
    and returns results ranked according to ``sort_by``.

    Sorting modes (first-principles analysis):
    - ``"balanced"`` (default): Maximize coverage among candidates whose
      delta_xy ≤ ``delta_threshold``.  This ensures the white point is
      reasonably close to target while prioritising gamut size.
    - ``"coverage"``: Sort purely by coverage (descending), then delta_xy
      (ascending).  Use when gamut size is the only priority.
    - ``"match"``: Sort by match (actual intersection with target gamut,
      descending), then delta_xy.  Use when overlap with target matters
      more than absolute gamut size.
    - ``"delta_xy"``: Legacy mode — sort by delta_xy (ascending), then
      coverage (descending).  Prioritises white-point accuracy.

    Args:
        sources: Primary source spectra [R, G, B].
        cfs: Color filter (absorber) spectra [RCF, GCF, BCF].
        bounds: Per-channel (min, max) thickness bounds in μm.
        target_xy: Target white-point chromaticity.
        target_standard: Gamut standard name for coverage/match (default "BT2020").
        steps: Grid resolution per channel (default 10 → 1000 combos).
        sort_by: Sorting strategy (see above).
        delta_threshold: Max acceptable delta_xy for ``"balanced"`` mode.
        progress_callback: Invoked with 0-100 percent during search.
        cancel_check: If returns True, search is aborted early.

    Returns:
        List of result dicts, sorted per ``sort_by``, limited to top 5.
        Each dict has keys: thickness_r/g/b, white_xy, delta_xy, coverage, match, rank.
    """
    if len(sources) != 3:
        raise ValueError(f"Expected 3 source spectra, got {len(sources)}")
    if len(cfs) != 3:
        raise ValueError(f"Expected 3 CF spectra, got {len(cfs)}")
    if len(bounds) != 3:
        raise ValueError(f"Expected 3 bounds, got {len(bounds)}")
    for i, (lo, hi) in enumerate(bounds):
        if lo < 0 or hi < 0:
            raise ValueError(
                f"Thickness bounds must be non-negative; channel {i} "
                f"got (lo={lo}, hi={hi})"
            )
    if not isinstance(steps, int) or steps < 2:
        raise ValueError(f"steps must be an integer >= 2, got {steps}")
    if steps > 50:
        raise ValueError(f"steps must be <= 50 to prevent excessive computation (steps^3={steps**3}), got {steps}")
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

    # Filter out degenerate candidates (zero-intensity spectra → delta_xy=inf).
    candidates = [c for c in candidates if c["delta_xy"] != float("inf")]

    # Sort according to the selected strategy.
    valid_modes = {"balanced", "coverage", "match", "delta_xy"}
    if sort_by not in valid_modes:
        raise ValueError(
            f"sort_by must be one of {valid_modes}, got {sort_by!r}"
        )

    if sort_by == "delta_xy":
        # Legacy: white-point accuracy first.
        candidates.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
    elif sort_by == "coverage":
        # Pure gamut size priority.
        candidates.sort(key=lambda x: (-x["coverage"], x["delta_xy"]))
    elif sort_by == "match":
        # Actual overlap with target gamut.
        candidates.sort(key=lambda x: (-x["match"], x["delta_xy"]))
    else:
        # Balanced: maximize coverage among candidates with acceptable delta_xy.
        # Candidates within threshold are sorted by coverage (desc);
        # candidates outside threshold are sorted by delta_xy (asc) and
        # placed after the within-threshold group.
        within = [c for c in candidates if c["delta_xy"] <= delta_threshold]
        outside = [c for c in candidates if c["delta_xy"] > delta_threshold]
        within.sort(key=lambda x: (-x["coverage"], x["delta_xy"]))
        outside.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
        candidates = within + outside

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
    if not 0 <= vary_channel < 3:
        raise ValueError(f"vary_channel must be 0, 1, or 2, got {vary_channel}")
    if len(bounds) != 3:
        raise ValueError(f"Expected 3 bounds, got {len(bounds)}")
    if len(base_thicknesses) != 3:
        raise ValueError(
            f"Expected 3 base_thicknesses, got {len(base_thicknesses)}"
        )
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
        for src, alpha, dd in zip(src_vals, alphas, ds, strict=True):
            t = np.power(10.0, -alpha * dd)
            filtered.append(src * t)
        white_vals = np.sum(np.stack(filtered), axis=0)
        total_intensity = float(np.sum(white_vals))
        if total_intensity < 1e-12:
            points.append({
                "thickness": float(d),
                "coverage": 0.0,
                "white_x": float("nan"),
                "white_y": float("nan"),
            })
            continue
        white_spec = Spectrum(wavelengths=wavelengths, values=white_vals, unit=unit)
        white_xy = spectrum_xy(white_spec)
        if np.isnan(white_xy.x) or np.isnan(white_xy.y):
            points.append({
                "thickness": float(d),
                "coverage": 0.0,
                "white_x": float("nan"),
                "white_y": float("nan"),
            })
            continue
        primaries_xy = [
            spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=unit))
            for v in filtered
        ]
        # Guard against NaN in any primary channel (consistent with
        # _compute_single_candidate).  When one CF is so thick that the
        # filtered spectrum is effectively zero, spectrum_xy returns NaN,
        # which would crash build_gamut_from_primaries.
        if any(np.isnan(p.x) or np.isnan(p.y) for p in primaries_xy):
            points.append({
                "thickness": float(d),
                "coverage": 0.0,
                "white_x": float(white_xy.x),
                "white_y": float(white_xy.y),
            })
            continue
        device = build_gamut_from_primaries(
            "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
        )
        cov = coverage(target_gamut, device)
        points.append({
            "thickness": float(d),
            "coverage": float(cov),
            "white_x": float(white_xy.x),
            "white_y": float(white_xy.y),
        })
    return points


def sensitivity_all_channels(
    sources: list[Spectrum],
    cfs: list[Spectrum],
    bounds: list[tuple[float, float]],
    base_thicknesses: list[float],
    target_xy: XY,
    target_standard: str = "BT2020",
    steps: int = 21,
    *,
    progress_callback: Callable[[int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, list[dict]]:
    """Run sensitivity analysis for all three channels.

    Args:
        sources: Primary source spectra [R, G, B].
        cfs: Color filter spectra [RCF, GCF, BCF].
        bounds: Per-channel (min, max) thickness bounds.
        base_thicknesses: Best thicknesses [R, G, B] to fix the other channels.
        target_xy: Target white-point chromaticity.
        target_standard: Gamut standard for coverage.
        steps: Number of sample points along the thickness range.
        progress_callback: Invoked with 0-100 percent.
        cancel_check: If returns True, aborts early.

    Returns:
        Dict mapping channel name ("R"/"G"/"B") to list of {thickness, coverage} dicts.
    """
    if len(bounds) != 3:
        raise ValueError(f"Expected 3 bounds, got {len(bounds)}")
    if len(base_thicknesses) != 3:
        raise ValueError(f"Expected 3 base_thicknesses, got {len(base_thicknesses)}")

    results: dict[str, list[dict]] = {}
    for ch_idx in range(3):
        ch_name = ["R", "G", "B"][ch_idx]

        def _cumulative_cb(pct: int, _ch_idx: int = ch_idx) -> None:
            if progress_callback:
                progress_callback(int((_ch_idx * 100 + pct) / 3))

        points = sensitivity_analysis(
            sources, cfs, bounds, base_thicknesses, ch_idx, target_xy,
            target_standard=target_standard, steps=steps,
            progress_callback=_cumulative_cb,
            cancel_check=cancel_check,
        )
        results[ch_name] = points
    return results


# ---------------------------------------------------------------------------
# Model 4: CF material selection (Filter 2)
# ---------------------------------------------------------------------------


def select_cf_materials(
    sources: list[Spectrum],
    cf_library: dict[str, list[Spectrum]],
    thicknesses: list[float],
    target_xy: XY,
    target_standard: str = "BT2020",
    *,
    progress_callback: Callable[[int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict]:
    """Select the best CF material combination for a target gamut.

    Given fixed emission spectra and CF thicknesses, this function
    enumerates all combinations of R/G/B CF materials from the provided
    library and ranks them by delta-xy (ascending) then coverage
    (descending).

    Args:
        sources: Primary source spectra [R, G, B] (fixed).
        cf_library: Dictionary mapping channel name to list of candidate
            CF spectra.  Keys must include "R", "G", "B".  Each value is
            a list of Spectrum objects (transmittance or absorption).
        thicknesses: Fixed CF thicknesses [R, G, B] in μm.
        target_xy: Target white-point chromaticity.
        target_standard: Gamut standard name for coverage/match.
        progress_callback: Invoked with 0-100 percent.
        cancel_check: If returns True, aborts early.

    Returns:
        List of result dicts sorted by (delta_xy, -coverage), top 10.
        Each dict has keys: cf_r_name, cf_g_name, cf_b_name,
        white_xy, delta_xy, coverage, match, rank.
    """
    target_gamut = standard_gamuts(target_standard)

    cf_r_list = cf_library.get("R", [])
    cf_g_list = cf_library.get("G", [])
    cf_b_list = cf_library.get("B", [])

    if not cf_r_list or not cf_g_list or not cf_b_list:
        raise ValueError("CF library must contain non-empty lists for R, G, B")
    if len(sources) != 3:
        raise ValueError(f"Expected 3 source spectra, got {len(sources)}")
    if len(thicknesses) != 3:
        raise ValueError(f"Expected 3 thicknesses, got {len(thicknesses)}")

    # Pre-compute the common wavelength grid from sources and all CF candidates.
    all_cfs = cf_r_list + cf_g_list + cf_b_list
    wavelengths = np.round(sources[0].wavelengths, 1)
    for s in sources[1:]:
        wavelengths = np.intersect1d(wavelengths, np.round(s.wavelengths, 1))
    for c in all_cfs:
        wavelengths = np.intersect1d(wavelengths, np.round(c.wavelengths, 1))
    if len(wavelengths) < 3:
        raise ValueError("Insufficient common wavelength points between spectra")

    def _resample(spec: Spectrum) -> NDArray[np.float64]:
        return np.interp(wavelengths, spec.wavelengths, spec.values)

    src_vals = [_resample(s) for s in sources]
    unit = sources[0].unit

    # Pre-compute alpha for all CF candidates (avoid redundant _prepare_grid_inputs calls).
    alpha_r_list = [_transmittance_to_alpha(_resample(c), c.meta) for c in cf_r_list]
    alpha_g_list = [_transmittance_to_alpha(_resample(c), c.meta) for c in cf_g_list]
    alpha_b_list = [_transmittance_to_alpha(_resample(c), c.meta) for c in cf_b_list]

    total = len(cf_r_list) * len(cf_g_list) * len(cf_b_list)
    candidates: list[dict] = []
    count = 0

    for ir, (cf_r, alpha_r) in enumerate(zip(cf_r_list, alpha_r_list, strict=True)):
        for ig, (cf_g, alpha_g) in enumerate(zip(cf_g_list, alpha_g_list, strict=True)):
            for ib, (cf_b, alpha_b) in enumerate(zip(cf_b_list, alpha_b_list, strict=True)):
                count += 1
                if cancel_check and cancel_check():
                    return []
                if progress_callback and count % 10 == 0:
                    progress_callback(int(100 * count / total))

                alphas = [alpha_r, alpha_g, alpha_b]
                result = _compute_single_candidate(
                    wavelengths, src_vals, alphas,
                    thicknesses, target_xy, target_gamut, unit,
                )
                result["cf_r_name"] = cf_r.meta.get("name", f"R-{ir}")
                result["cf_g_name"] = cf_g.meta.get("name", f"G-{ig}")
                result["cf_b_name"] = cf_b.meta.get("name", f"B-{ib}")
                candidates.append(result)

    # Filter out degenerate candidates (zero-intensity spectra → delta_xy=inf).
    candidates = [c for c in candidates if c["delta_xy"] != float("inf")]
    candidates.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
    top = candidates[:10]
    for i, r in enumerate(top):
        r["rank"] = i + 1
    return top


# ---------------------------------------------------------------------------
# Model 5: Emission spectrum optimization (Filter 3)
# ---------------------------------------------------------------------------

from colorlab_pro.engines.spectrum_manipulator import (
    adjust_qd_full,
    scale_fwhm,
    translate_spectrum,
)


def _adjust_single_emission(
    source: Spectrum,
    peak_delta: float,
    fwhm_factor: float,
    is_qd: bool,
    b_led: Spectrum | None,
    old_b_led: Spectrum | None,
    new_b_led: Spectrum | None,
    blue_cutoff: float = 500.0,
) -> Spectrum:
    """Adjust a single emission spectrum.

    For non-QD spectra (e.g. B-LED), apply translate + scale directly.
    For QD spectra, use ``adjust_qd_full`` to handle blue leakage.

    Args:
        source: Original emission spectrum.
        peak_delta: Wavelength shift in nm.
        fwhm_factor: FWHM scaling factor.
        is_qd: Whether this is a QD spectrum (needs leakage handling).
        b_led: B-LED spectrum (for QD separation, use original if no B-LED change).
        old_b_led: Original B-LED (before adjustment), or None.
        new_b_led: Adjusted B-LED, or None.
        blue_cutoff: Wavelength separating blue leakage from QD emission.

    Returns:
        Adjusted Spectrum.
    """
    if not is_qd:
        adjusted = source
        if abs(peak_delta) > 1e-6:
            adjusted = translate_spectrum(adjusted, peak_delta)
        if abs(fwhm_factor - 1.0) > 1e-6:
            adjusted = scale_fwhm(adjusted, fwhm_factor)
        return adjusted

    # QD spectrum: handle blue leakage.
    if b_led is None:
        # No B-LED available, treat as non-QD.
        adjusted = source
        if abs(peak_delta) > 1e-6:
            adjusted = translate_spectrum(adjusted, peak_delta)
        if abs(fwhm_factor - 1.0) > 1e-6:
            adjusted = scale_fwhm(adjusted, fwhm_factor)
        return adjusted

    if new_b_led is not None and old_b_led is not None:
        # Both QD emission and B-LED are being adjusted.
        return adjust_qd_full(
            source, old_b_led, new_b_led,
            peak_delta=peak_delta,
            fwhm_factor=fwhm_factor,
            blue_cutoff=blue_cutoff,
        )
    else:
        # Only QD emission is being adjusted, B-LED stays the same.
        from colorlab_pro.engines.spectrum_manipulator import adjust_qd_emission

        return adjust_qd_emission(
            source, b_led,
            peak_delta=peak_delta,
            fwhm_factor=fwhm_factor,
            blue_cutoff=blue_cutoff,
        )


def optimize_emission_spectra(
    sources: list[Spectrum],
    cfs: list[Spectrum],
    thicknesses: list[float],
    target_xy: XY,
    target_standard: str = "BT2020",
    peak_ranges: list[tuple[float, float]] | None = None,
    fwhm_ranges: list[tuple[float, float]] | None = None,
    is_qd: list[bool] | None = None,
    blue_cutoff: float = 500.0,
    steps: int = 5,
    *,
    progress_callback: Callable[[int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict]:
    """Optimise emission spectra by adjusting peak wavelength and FWHM.

    Each of the R/G/B emission spectra can be independently adjusted:
    - Peak wavelength shift via ``translate_spectrum``.
    - FWHM scaling via ``scale_fwhm``.

    For QD spectra (QD-R, QD-G), the blue leakage component is preserved
    when only the QD emission is adjusted.  When the B-LED (blue emission)
    spectrum is also adjusted, the QD blue leakage is updated
    proportionally to the new B-LED shape.

    The search is a grid search over (peak_delta, fwhm_factor) for each
    channel.  With ``steps=5`` and 3 channels, the total is 5²×3 = 75
    combinations per channel, but since channels are independent, the
    total search space is (5²)³ = 15,625.  To keep computation feasible,
    ``steps`` should be kept small (3-7).

    Args:
        sources: Original primary source spectra [R, G, B].
        cfs: Color filter spectra [RCF, GCF, BCF].
        thicknesses: Fixed CF thicknesses [R, G, B] in μm.
        target_xy: Target white-point chromaticity.
        target_standard: Gamut standard name.
        peak_ranges: Per-channel (min_delta, max_delta) for peak shift
            in nm.  Default: [(-10, 10), (-10, 10), (-10, 10)].
        fwhm_ranges: Per-channel (min_factor, max_factor) for FWHM
            scaling.  Default: [(0.7, 1.5), (0.7, 1.5), (0.7, 1.5)].
        is_qd: Per-channel flag indicating QD spectra.  Default:
            [True, True, False] (QD-R, QD-G, B-LED).
        blue_cutoff: Wavelength separating blue leakage from QD emission.
        steps: Grid resolution per parameter per channel.
        progress_callback: Invoked with 0-100 percent.
        cancel_check: If returns True, aborts early.

    Returns:
        List of result dicts sorted by (delta_xy, -coverage), top 10.
        Each dict has keys: peak_deltas, fwhm_factors, white_xy,
        delta_xy, coverage, match, rank.
    """
    target_gamut = standard_gamuts(target_standard)

    if peak_ranges is None:
        peak_ranges = [(-10.0, 10.0)] * 3
    if fwhm_ranges is None:
        fwhm_ranges = [(0.7, 1.5)] * 3
    if is_qd is None:
        is_qd = [True, True, False]

    # Validate inputs
    if len(sources) != 3:
        raise ValueError(f"Expected 3 source spectra, got {len(sources)}")
    if len(cfs) != 3:
        raise ValueError(f"Expected 3 CF spectra, got {len(cfs)}")
    if len(thicknesses) != 3:
        raise ValueError(f"Expected 3 thicknesses, got {len(thicknesses)}")
    if len(peak_ranges) != 3:
        raise ValueError(f"Expected 3 peak_ranges, got {len(peak_ranges)}")
    if len(fwhm_ranges) != 3:
        raise ValueError(f"Expected 3 fwhm_ranges, got {len(fwhm_ranges)}")
    if len(is_qd) != 3:
        raise ValueError(f"Expected 3 is_qd flags, got {len(is_qd)}")
    if not isinstance(steps, int) or steps < 2:
        raise ValueError(f"steps must be an integer >= 2, got {steps}")
    if steps > 10:
        raise ValueError(f"steps must be <= 10 to prevent excessive computation (steps^6={steps**6}), got {steps}")

    # Pre-compute CF alpha coefficients on common wavelength grid.
    wavelengths, _, alphas, unit = _prepare_grid_inputs(sources, cfs)

    # Generate grid points for each channel.
    peak_grids = [
        np.linspace(pr[0], pr[1], steps) for pr in peak_ranges
    ]
    fwhm_grids = [
        np.linspace(fr[0], fr[1], steps) for fr in fwhm_ranges
    ]

    total = steps ** 6
    candidates: list[dict] = []
    count = 0

    # Store original B-LED for QD leakage handling.
    original_b_led = sources[2]

    # Import QD separation for optimization.
    from colorlab_pro.engines.spectrum_manipulator import (
        separate_qd_spectrum,
        translate_spectrum,
        scale_fwhm,
        compute_leakage_ratio,
    )

    # Pre-separate QD spectra for R and G channels (only needed once).
    qd_separated: dict[int, tuple] = {}  # {channel_idx: (blue_leakage, qd_emission, k)}
    for ch_idx in [0, 1]:
        if is_qd[ch_idx] and original_b_led is not None:
            bl, qd_em = separate_qd_spectrum(sources[ch_idx], original_b_led, blue_cutoff)
            k = bl.meta.get("leakage_ratio", 0.0)
            qd_separated[ch_idx] = (bl, qd_em, k)

    for pr in peak_grids[0]:
        for fr in fwhm_grids[0]:
            # Pre-compute adjusted QD emission for R (only depends on pr, fr).
            if 0 in qd_separated:
                _, qd_em_r, _ = qd_separated[0]
                adj_qd_em_r = qd_em_r
                if abs(pr) > 1e-6:
                    adj_qd_em_r = translate_spectrum(adj_qd_em_r, pr)
                if abs(fr - 1.0) > 1e-6:
                    adj_qd_em_r = scale_fwhm(adj_qd_em_r, fr)
            else:
                # Non-QD: pre-compute adjusted R spectrum.
                adj_r_base = sources[0]
                if abs(pr) > 1e-6:
                    adj_r_base = translate_spectrum(adj_r_base, pr)
                if abs(fr - 1.0) > 1e-6:
                    adj_r_base = scale_fwhm(adj_r_base, fr)

            for pg in peak_grids[1]:
                for fg in fwhm_grids[1]:
                    # Pre-compute adjusted QD emission for G (only depends on pg, fg).
                    if 1 in qd_separated:
                        _, qd_em_g, _ = qd_separated[1]
                        adj_qd_em_g = qd_em_g
                        if abs(pg) > 1e-6:
                            adj_qd_em_g = translate_spectrum(adj_qd_em_g, pg)
                        if abs(fg - 1.0) > 1e-6:
                            adj_qd_em_g = scale_fwhm(adj_qd_em_g, fg)
                    else:
                        adj_g_base = sources[1]
                        if abs(pg) > 1e-6:
                            adj_g_base = translate_spectrum(adj_g_base, pg)
                        if abs(fg - 1.0) > 1e-6:
                            adj_g_base = scale_fwhm(adj_g_base, fg)

                    for pb in peak_grids[2]:
                        for fb in fwhm_grids[2]:
                            count += 1
                            if cancel_check and cancel_check():
                                return []
                            if progress_callback and count % 50 == 0:
                                progress_callback(int(100 * count / total))

                            # Adjust B spectrum.
                            adj_b = sources[2]
                            if abs(pb) > 1e-6:
                                adj_b = translate_spectrum(adj_b, pb)
                            if abs(fb - 1.0) > 1e-6:
                                adj_b = scale_fwhm(adj_b, fb)

                            b_led_changed = abs(pb) > 1e-6 or abs(fb - 1.0) > 1e-6

                            # Compute final R spectrum.
                            if 0 in qd_separated:
                                _, _, k_r = qd_separated[0]
                                if b_led_changed:
                                    # New blue leakage = k_r * adj_b
                                    new_bl_r_vals = k_r * np.interp(
                                        sources[0].wavelengths,
                                        adj_b.wavelengths,
                                        adj_b.values,
                                        left=0.0, right=0.0,
                                    )
                                    adj_r_final = Spectrum(
                                        wavelengths=sources[0].wavelengths.copy(),
                                        values=new_bl_r_vals + adj_qd_em_r.values,
                                        unit=sources[0].unit,
                                        meta={**sources[0].meta, "emission_adjusted": True},
                                    )
                                else:
                                    # Use original blue leakage + adjusted QD emission.
                                    bl_r, _, _ = qd_separated[0]
                                    adj_r_final = Spectrum(
                                        wavelengths=sources[0].wavelengths.copy(),
                                        values=bl_r.values + adj_qd_em_r.values,
                                        unit=sources[0].unit,
                                        meta={**sources[0].meta, "emission_adjusted": True},
                                    )
                            else:
                                adj_r_final = adj_r_base

                            # Compute final G spectrum.
                            if 1 in qd_separated:
                                _, _, k_g = qd_separated[1]
                                if b_led_changed:
                                    new_bl_g_vals = k_g * np.interp(
                                        sources[1].wavelengths,
                                        adj_b.wavelengths,
                                        adj_b.values,
                                        left=0.0, right=0.0,
                                    )
                                    adj_g_final = Spectrum(
                                        wavelengths=sources[1].wavelengths.copy(),
                                        values=new_bl_g_vals + adj_qd_em_g.values,
                                        unit=sources[1].unit,
                                        meta={**sources[1].meta, "emission_adjusted": True},
                                    )
                                else:
                                    bl_g, _, _ = qd_separated[1]
                                    adj_g_final = Spectrum(
                                        wavelengths=sources[1].wavelengths.copy(),
                                        values=bl_g.values + adj_qd_em_g.values,
                                        unit=sources[1].unit,
                                        meta={**sources[1].meta, "emission_adjusted": True},
                                    )
                            else:
                                adj_g_final = adj_g_base

                            # Compute filtered spectra and gamut.
                            adj_sources = [adj_r_final, adj_g_final, adj_b]
                            adj_vals = [
                                np.interp(wavelengths, s.wavelengths, s.values,
                                          left=0.0, right=0.0)
                                for s in adj_sources
                            ]

                            result = _compute_single_candidate(
                                wavelengths, adj_vals, alphas,
                                thicknesses, target_xy, target_gamut, unit,
                            )
                            result["peak_deltas"] = [
                                round(float(pr), 2),
                                round(float(pg), 2),
                                round(float(pb), 2),
                            ]
                            result["fwhm_factors"] = [
                                round(float(fr), 3),
                                round(float(fg), 3),
                                round(float(fb), 3),
                            ]
                            candidates.append(result)

    # Filter out degenerate candidates (zero-intensity spectra → delta_xy=inf).
    candidates = [c for c in candidates if c["delta_xy"] != float("inf")]
    candidates.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
    top = candidates[:10]
    for i, r in enumerate(top):
        r["rank"] = i + 1
    return top
