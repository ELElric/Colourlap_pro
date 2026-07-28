"""OptimizationService orchestrates white-point and thickness optimizations."""

from __future__ import annotations

import json
from collections.abc import Callable

from sqlalchemy.orm import Session

from colorlab_pro.database.models import Optimization
from colorlab_pro.dto.color import XY, OptimizationResult
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.thickness_optimizer import (
    grid_search_optimize,
    optimize_thickness,
    optimize_emission_spectra,
    select_cf_materials,
    sensitivity_analysis,
    sensitivity_all_channels,
)
from colorlab_pro.engines.white_point_calculator import (
    delta_xy_to_target,
    mixing_weights,
    nearest_white_point,
)


class OptimizationService:
    """Service for white-point mixing and color-filter thickness optimization."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Initialize with a factory that produces SQLAlchemy sessions.

        Args:
            session_factory: Callable returning a new ORM session.
        """
        self._session_factory = session_factory

    def optimize_white_point(
        self,
        primaries: list[Spectrum],
        target_xy: XY,
    ) -> dict[str, object]:
        """Compute per-channel weights to match a target white point.

        Returns a dictionary with keys:
        - ``weights``: list of non-negative weights
        - ``achieved_xy``: achieved XY chromaticity
        - ``delta_xy``: Euclidean error in xy
        - ``nearest_white_point``: name of the nearest standard white point
        """
        weights, achieved_xy = mixing_weights(primaries, target_xy, normalize=True)
        delta_xy = delta_xy_to_target(primaries, target_xy)
        nearest_name, _distance = nearest_white_point(achieved_xy)

        return {
            "weights": [float(w) for w in weights],
            "achieved_xy": achieved_xy,
            "delta_xy": delta_xy,
            "nearest_white_point": nearest_name,
        }

    def optimize_thickness(
        self,
        target_xy: XY,
        source_spectrum: Spectrum,
        absorbers: list[Spectrum],
        bounds_um: tuple[float, float] = (0.1, 10.0),
    ) -> OptimizationResult:
        """Optimize color-filter thicknesses to match a target xy."""
        return optimize_thickness(target_xy, source_spectrum, absorbers, bounds_um=bounds_um)

    # ------------------------------------------------------------------ #
    # Grid search & sensitivity
    # ------------------------------------------------------------------ #

    def grid_search_optimize(
        self,
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
        """Grid-search thickness optimization for 3-channel display model."""
        return grid_search_optimize(
            sources, cfs, bounds, target_xy,
            target_standard=target_standard, steps=steps,
            progress_callback=progress_callback, cancel_check=cancel_check,
        )

    def sensitivity_analysis(
        self,
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
        """Single-channel sensitivity analysis."""
        return sensitivity_analysis(
            sources, cfs, bounds, base_thicknesses, vary_channel, target_xy,
            target_standard=target_standard, steps=steps,
            progress_callback=progress_callback, cancel_check=cancel_check,
        )

    def sensitivity_all_channels(
        self,
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
        """Run sensitivity analysis for all three channels."""
        return sensitivity_all_channels(
            sources, cfs, bounds, base_thicknesses,
            target_standard=target_standard, steps=steps,
            progress_callback=progress_callback, cancel_check=cancel_check,
        )

    # ------------------------------------------------------------------ #
    # CF material selection (Filter 2)
    # ------------------------------------------------------------------ #

    def select_cf_materials(
        self,
        sources: list[Spectrum],
        cf_library: dict[str, list[Spectrum]],
        thicknesses: list[float],
        target_xy: XY,
        target_standard: str = "BT2020",
        *,
        progress_callback: Callable[[int], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[dict]:
        """Select the best CF material combination for a target gamut."""
        return select_cf_materials(
            sources, cf_library, thicknesses, target_xy,
            target_standard=target_standard,
            progress_callback=progress_callback, cancel_check=cancel_check,
        )

    # ------------------------------------------------------------------ #
    # Emission spectrum optimization (Filter 3)
    # ------------------------------------------------------------------ #

    def optimize_emission_spectra(
        self,
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
        """Optimise emission spectra by adjusting peak wavelength and FWHM."""
        return optimize_emission_spectra(
            sources, cfs, thicknesses, target_xy,
            target_standard=target_standard,
            peak_ranges=peak_ranges,
            fwhm_ranges=fwhm_ranges,
            is_qd=is_qd,
            blue_cutoff=blue_cutoff,
            steps=steps,
            progress_callback=progress_callback, cancel_check=cancel_check,
        )

    def save_optimization(
        self,
        project_id: int,
        name: str,
        target_xy: XY,
        result: OptimizationResult,
    ) -> int:
        """Persist an optimization result and return its id."""
        result_json = json.dumps(
            {
                "thicknesses_um": result.thicknesses_um,
                "achieved_xy": (result.achieved_xy.x, result.achieved_xy.y),
                "target_xy": (result.target_xy.x, result.target_xy.y),
                "delta_xy": result.delta_xy,
                "converged": result.converged,
                "iterations": result.iterations,
                "meta": result.meta,
            },
            ensure_ascii=False,
        )

        with self._session_factory() as session:
            opt = Optimization(
                project_id=project_id,
                name=name,
                target_xy_x=target_xy.x,
                target_xy_y=target_xy.y,
                result_json=result_json,
            )
            session.add(opt)
            session.flush()
            session.commit()
            return int(opt.id)
