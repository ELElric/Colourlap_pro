"""Tests for OptimizationController."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import (
    OptimizationController,
    ThicknessResult,
    WhitePointResult,
)
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.dto.color import XY, OptimizationResult
from colorlab_pro.dto.spectrum import Spectrum


@pytest.fixture
def opt_ctrl(tmp_path: Path, qtbot):
    """Provide an OptimizationController with a project and in-memory DB."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    proj_ctrl = ProjectController(main)
    pid = proj_ctrl.create_project("Opt Project")
    main.set_current_project(pid)

    ctrl = OptimizationController(main)
    yield ctrl
    main.shutdown()


def _make_spec(peak_wl: float) -> Spectrum:
    """Create a 1nm-step Gaussian spectrum."""
    wls = np.arange(380.0, 781.0, 1.0)
    values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
    return Spectrum(wavelengths=wls, values=values)


class TestWhitePoint:
    def test_optimize_white_point(self, opt_ctrl: OptimizationController, qtbot) -> None:
        red = _make_spec(620.0)
        green = _make_spec(520.0)
        blue = _make_spec(460.0)
        target = XY(x=0.3127, y=0.3290)
        with qtbot.waitSignal(opt_ctrl.white_point_ready, timeout=1000):
            result = opt_ctrl.optimize_white_point([red, green, blue], target)
        assert result is not None
        assert isinstance(result, WhitePointResult)
        assert len(result.weights) == 3
        assert result.delta_xy >= 0


class TestThickness:
    def test_optimize_thickness(self, opt_ctrl: OptimizationController, qtbot) -> None:
        source = _make_spec(550.0)
        absorber1 = _make_spec(600.0)
        absorber2 = _make_spec(500.0)
        target = XY(x=0.3, y=0.3)
        with qtbot.waitSignal(opt_ctrl.thickness_ready, timeout=1000):
            result = opt_ctrl.optimize_thickness(target, source, [absorber1, absorber2])
        assert result is not None
        assert isinstance(result, ThicknessResult)
        assert len(result.thicknesses_um) == 2


class TestSave:
    def test_save_optimization(self, opt_ctrl: OptimizationController, qtbot) -> None:
        opt_result = OptimizationResult(
            thicknesses_um=[1.0, 2.0],
            achieved_xy=XY(x=0.3, y=0.3),
            target_xy=XY(x=0.3127, y=0.3290),
            delta_xy=0.01,
            converged=True,
            iterations=10,
        )
        with qtbot.waitSignal(opt_ctrl.optimization_saved, timeout=1000):
            oid = opt_ctrl.save_optimization("Test Opt", XY(x=0.3127, y=0.3290), opt_result)
        assert oid is not None
        assert isinstance(oid, int)

    def test_save_without_project(self, opt_ctrl: OptimizationController, qtbot) -> None:
        opt_ctrl._main.set_current_project(None)
        opt_result = OptimizationResult(
            thicknesses_um=[1.0],
            achieved_xy=XY(x=0.3, y=0.3),
            target_xy=XY(x=0.3127, y=0.3290),
            delta_xy=0.01,
            converged=True,
            iterations=5,
        )
        with qtbot.waitSignal(opt_ctrl.error_occurred, timeout=1000):
            result = opt_ctrl.save_optimization("Test", XY(x=0.3127, y=0.3290), opt_result)
        assert result is None


class TestServiceAvailability:
    def test_optimization_service_unavailable(self, opt_ctrl: OptimizationController) -> None:
        opt_ctrl._main.optimization_service = None
        with pytest.raises(RuntimeError, match="OptimizationService not available"):
            opt_ctrl._service()


class TestOptimizationErrors:
    def _make_spec(self, peak_wl: float) -> Spectrum:
        wls = np.arange(380.0, 781.0, 1.0)
        values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
        return Spectrum(wavelengths=wls, values=values)

    def test_optimize_white_point_exception(self, opt_ctrl: OptimizationController, qtbot) -> None:
        red = self._make_spec(620.0)
        green = self._make_spec(520.0)
        blue = self._make_spec(460.0)
        target = XY(x=0.3127, y=0.3290)
        opt_ctrl._main.optimization_service.optimize_white_point = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("opt failed"))
        with qtbot.waitSignal(opt_ctrl.error_occurred, timeout=1000):
            result = opt_ctrl.optimize_white_point([red, green, blue], target)
        assert result is None

    def test_optimize_thickness_exception(self, opt_ctrl: OptimizationController, qtbot) -> None:
        source = self._make_spec(550.0)
        absorber = self._make_spec(600.0)
        target = XY(x=0.3, y=0.3)
        opt_ctrl._main.optimization_service.optimize_thickness = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("opt failed"))
        with qtbot.waitSignal(opt_ctrl.error_occurred, timeout=1000):
            result = opt_ctrl.optimize_thickness(target, source, [absorber])
        assert result is None
