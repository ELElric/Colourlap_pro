"""OptimizationController — manages white-point and thickness optimization.

Mediates between the Optimize page and OptimizationService.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from colorlab_pro.utils.signal import QObject, Signal

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.dto.color import XY, OptimizationResult
from colorlab_pro.dto.spectrum import Spectrum


@dataclass(frozen=True)
class WhitePointResult:
    """Result of a white-point optimization."""

    weights: list[float]
    achieved_xy: XY
    delta_xy: float
    nearest_white_point: str


@dataclass(frozen=True)
class ThicknessResult:
    """Result of a thickness optimization."""

    thicknesses_um: list[float]
    achieved_xy: XY
    target_xy: XY
    delta_xy: float
    converged: bool
    iterations: int


class OptimizationController(QObject):
    """Controller for optimization operations."""

    # Emitted when a white-point optimization completes.
    white_point_ready = Signal(object)

    # Emitted when a thickness optimization completes.
    thickness_ready = Signal(object)

    # Emitted when an optimization is saved.
    optimization_saved = Signal(int)

    # Emitted on operation errors.
    error_occurred = Signal(str)

    # Emitted during grid search / sensitivity (0-100 percent).
    grid_search_progress = Signal(int)

    # Emitted when grid search completes with results.
    grid_search_ready = Signal(object)

    # Emitted when CF material selection completes.
    cf_materials_ready = Signal(object)

    # Emitted when emission spectrum optimization completes.
    emission_optimization_ready = Signal(object)

    def __init__(
        self,
        main_controller: MainController,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with a reference to MainController.

        Args:
            main_controller: The application-level coordinator.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._main = main_controller

    # ------------------------------------------------------------------ #
    # Internal helper
    # ------------------------------------------------------------------ #

    def _service(self):
        """Return the OptimizationService from MainController."""
        if self._main.optimization_service is None:
            raise RuntimeError("OptimizationService not available.")
        return self._main.optimization_service

    def _require_project(self) -> int:
        """Return the current project id or raise."""
        pid = self._main.current_project_id
        if pid is None:
            raise RuntimeError("No project selected.")
        return pid

    # ------------------------------------------------------------------ #
    # White-point optimization
    # ------------------------------------------------------------------ #

    def optimize_white_point(
        self,
        primaries: list[Spectrum],
        target_xy: XY,
    ) -> WhitePointResult | None:
        """Optimize mixing weights to match a target white point.

        Args:
            primaries: List of primary spectra (typically R, G, B).
            target_xy: Target chromaticity.

        Returns:
            WhitePointResult or None on error.
        """
        try:
            raw = self._service().optimize_white_point(primaries, target_xy)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"White-point optimization failed: {exc}")
            return None

        result = WhitePointResult(
            weights=raw["weights"],
            achieved_xy=raw["achieved_xy"],
            delta_xy=raw["delta_xy"],
            nearest_white_point=raw["nearest_white_point"],
        )
        self.white_point_ready.emit(result)
        return result

    # ------------------------------------------------------------------ #
    # Thickness optimization
    # ------------------------------------------------------------------ #

    def optimize_thickness(
        self,
        target_xy: XY,
        source_spectrum: Spectrum,
        absorbers: list[Spectrum],
        bounds_um: tuple[float, float] = (0.1, 10.0),
    ) -> ThicknessResult | None:
        """Optimize color-filter thicknesses (stacked-filter model).

        Args:
            target_xy: Target chromaticity.
            source_spectrum: Source spectrum.
            absorbers: List of absorber spectra.
            bounds_um: Thickness bounds in micrometers.

        Returns:
            ThicknessResult or None on error.
        """
        try:
            # Validate thickness bounds.
            try:
                lo, hi = float(bounds_um[0]), float(bounds_um[1])
            except Exception as exc:  # noqa: BLE001
                raise ValueError("bounds_um must be a (min, max) pair") from exc
            if math.isnan(lo) or math.isinf(lo) or math.isnan(hi) or math.isinf(hi):
                raise ValueError("bounds_um values must be finite numbers")
            if lo < 0 or hi < 0:
                raise ValueError("bounds_um values must be non-negative")
            if lo >= hi:
                raise ValueError("bounds_um min must be less than max")
            bounds_um = (lo, hi)

            opt: OptimizationResult = self._service().optimize_thickness(
                target_xy, source_spectrum, absorbers, bounds_um=bounds_um
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Thickness optimization failed: {exc}")
            return None

        result = ThicknessResult(
            thicknesses_um=opt.thicknesses_um,
            achieved_xy=opt.achieved_xy,
            target_xy=opt.target_xy,
            delta_xy=opt.delta_xy,
            converged=opt.converged,
            iterations=opt.iterations,
        )
        self.thickness_ready.emit(result)
        return result

    def optimize_thickness_display(
        self,
        target_xy: XY,
        source_spectra: list[Spectrum],
        absorbers: list[Spectrum],
        bounds_um: list[tuple[float, float]] | None = None,
    ) -> ThicknessResult | None:
        """Optimize CF thicknesses (display model) to match a target white point.

        Each primary source passes through its own CF, then the filtered
        spectra are summed. This is the physically correct model for an RGB
        display.

        Args:
            target_xy: Target white-point chromaticity.
            source_spectra: List of primary source spectra [R, G, B].
            absorbers: List of absorption coefficient spectra [RCF, GCF, BCF].
            bounds_um: Optional per-channel (min, max) bounds.

        Returns:
            ThicknessResult or None on error.
        """
        try:
            from colorlab_pro.engines.thickness_optimizer import (
                optimize_thickness_display,
            )

            opt = optimize_thickness_display(
                target_xy, source_spectra, absorbers, bounds_um=bounds_um
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Thickness optimization failed: {exc}")
            return None

        result = ThicknessResult(
            thicknesses_um=list(opt.thicknesses_um),
            achieved_xy=opt.achieved_xy,
            target_xy=opt.target_xy,
            delta_xy=opt.delta_xy,
            converged=opt.converged,
            iterations=opt.iterations,
        )
        self.thickness_ready.emit(result)
        return result

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save_optimization(
        self,
        name: str,
        target_xy: XY,
        result: OptimizationResult,
    ) -> int | None:
        """Save an optimization result to the current project.

        Args:
            name: Optimization name.
            target_xy: Target chromaticity.
            result: OptimizationResult to save.

        Returns:
            The saved optimization id, or None on error.
        """
        try:
            project_id = self._require_project()
            opt_id = self._service().save_optimization(project_id, name, target_xy, result)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to save optimization: {exc}")
            return None

        self.optimization_saved.emit(opt_id)
        return opt_id

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
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[dict] | None:
        """Grid-search thickness optimization with progress signals.

        Emits ``grid_search_progress`` (0-100) during search and
        ``grid_search_ready`` with the result list on completion.
        """
        try:
            results = self._service().grid_search_optimize(
                sources, cfs, bounds, target_xy,
                target_standard=target_standard, steps=steps,
                progress_callback=lambda pct: self.grid_search_progress.emit(pct),
                cancel_check=cancel_check,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Grid search failed: {exc}")
            return None

        self.grid_search_ready.emit(results)
        return results

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
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[dict] | None:
        """Single-channel sensitivity analysis with progress signals."""
        try:
            points = self._service().sensitivity_analysis(
                sources, cfs, bounds, base_thicknesses, vary_channel, target_xy,
                target_standard=target_standard, steps=steps,
                progress_callback=lambda pct: self.grid_search_progress.emit(pct),
                cancel_check=cancel_check,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Sensitivity analysis failed: {exc}")
            return None

        return points

    def sensitivity_all_channels(
        self,
        sources: list[Spectrum],
        cfs: list[Spectrum],
        bounds: list[tuple[float, float]],
        base_thicknesses: list[float],
        target_xy: XY,
        target_standard: str = "BT2020",
        steps: int = 21,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, list[dict]] | None:
        """Run sensitivity analysis for all three channels with progress signals."""
        try:
            results = self._service().sensitivity_all_channels(
                sources, cfs, bounds, base_thicknesses, target_xy,
                target_standard=target_standard, steps=steps,
                progress_callback=lambda pct: self.grid_search_progress.emit(pct),
                cancel_check=cancel_check,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Sensitivity all channels failed: {exc}")
            return None

        return results

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
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[dict] | None:
        """Select the best CF material combination with progress signals.

        Emits ``grid_search_progress`` during search and
        ``cf_materials_ready`` with the result list on completion.
        """
        try:
            results = self._service().select_cf_materials(
                sources, cf_library, thicknesses, target_xy,
                target_standard=target_standard,
                progress_callback=lambda pct: self.grid_search_progress.emit(pct),
                cancel_check=cancel_check,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"CF material selection failed: {exc}")
            return None

        self.cf_materials_ready.emit(results)
        return results

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
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[dict] | None:
        """Optimise emission spectra with progress signals.

        Emits ``grid_search_progress`` during search and
        ``emission_optimization_ready`` with the result list on completion.
        """
        try:
            results = self._service().optimize_emission_spectra(
                sources, cfs, thicknesses, target_xy,
                target_standard=target_standard,
                peak_ranges=peak_ranges,
                fwhm_ranges=fwhm_ranges,
                is_qd=is_qd,
                blue_cutoff=blue_cutoff,
                steps=steps,
                progress_callback=lambda pct: self.grid_search_progress.emit(pct),
                cancel_check=cancel_check,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Emission spectrum optimization failed: {exc}")
            return None

        self.emission_optimization_ready.emit(results)
        return results
