"""OptimizationController — manages white-point and thickness optimization.

Mediates between the Optimize page and OptimizationService.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

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
