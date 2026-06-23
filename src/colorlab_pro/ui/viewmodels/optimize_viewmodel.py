"""OptimizeViewModel — data model for the Optimize page."""

from __future__ import annotations

from PySide6.QtCore import Signal

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.optimization_controller import (
    OptimizationController,
    ThicknessResult,
    WhitePointResult,
)
from colorlab_pro.dto.color import XY, OptimizationResult
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.viewmodels.base import ViewModel


class OptimizeViewModel(ViewModel):
    """ViewModel for optimization operations state."""

    # Emitted when a white-point result is ready.
    white_point_changed = Signal(object)

    # Emitted when a thickness result is ready.
    thickness_changed = Signal(object)

    def __init__(
        self,
        controller: OptimizationController,
        color_controller: ColorController | None = None,
        parent: object | None = None,
    ) -> None:
        """Initialize with controller references.

        Args:
            controller: The optimization controller.
            color_controller: Optional color controller for gamut coverage.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._color_controller = color_controller
        self._wp_result: WhitePointResult | None = None
        self._th_result: ThicknessResult | None = None

        self._controller.white_point_ready.connect(self._on_wp_ready)
        self._controller.thickness_ready.connect(self._on_th_ready)
        self._controller.error_occurred.connect(self.set_error)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def white_point_result(self) -> WhitePointResult | None:
        return self._wp_result

    @property
    def thickness_result(self) -> ThicknessResult | None:
        return self._th_result

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def optimize_white_point(
        self,
        primaries: list[Spectrum],
        target_xy: XY,
    ) -> WhitePointResult | None:
        """Run white-point optimization."""
        self.set_status("Optimizing white point...")
        return self._controller.optimize_white_point(primaries, target_xy)

    def optimize_thickness(
        self,
        target_xy: XY,
        source: Spectrum,
        absorbers: list[Spectrum],
        bounds_um: tuple[float, float] = (0.1, 10.0),
    ) -> ThicknessResult | None:
        """Run thickness optimization."""
        self.set_status("Optimizing thickness...")
        return self._controller.optimize_thickness(
            target_xy, source, absorbers, bounds_um=bounds_um
        )

    def project_gamut_coverage(
        self,
        standard_name: str,
        spectra: list[Spectrum],
    ) -> dict | None:
        """Compute coverage/match of the first three spectra vs a standard gamut."""
        if self._color_controller is None:
            self.set_error("ColorController not available for gamut coverage.")
            return None
        self.set_status("Computing gamut coverage / match...")
        return self._color_controller.project_gamut_coverage(standard_name, spectra)

    def save_thickness_result(self, name: str) -> int | None:
        """Save the last thickness optimization result to the current project."""
        if self._th_result is None:
            self.set_error("No thickness result to save.")
            return None
        result = OptimizationResult(
            thicknesses_um=tuple(self._th_result.thicknesses_um),
            achieved_xy=self._th_result.achieved_xy,
            target_xy=self._th_result.target_xy,
            delta_xy=self._th_result.delta_xy,
            converged=self._th_result.converged,
            iterations=self._th_result.iterations,
        )
        return self._controller.save_optimization(name, result.target_xy, result)

    def _on_wp_ready(self, result: WhitePointResult) -> None:
        """Handle white-point results."""
        self._wp_result = result
        self.white_point_changed.emit(result)
        self.set_status("White-point optimization complete.")

    def _on_th_ready(self, result: ThicknessResult) -> None:
        """Handle thickness results."""
        self._th_result = result
        self.thickness_changed.emit(result)
        self.set_status("Thickness optimization complete.")
