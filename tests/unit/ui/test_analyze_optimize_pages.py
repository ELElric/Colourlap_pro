"""Tests for AnalyzePage and OptimizePage."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.pages.analyze_page import AnalyzePage
from colorlab_pro.ui.pages.optimize_page import OptimizePage


def _make_spec(peak_wl: float) -> Spectrum:
    wls = np.arange(380.0, 781.0, 1.0)
    values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
    return Spectrum(wavelengths=wls, values=values)


@pytest.fixture
def analyze_page(tmp_path: Path, qtbot):
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    proj_ctrl = ProjectController(main)
    pid = proj_ctrl.create_project("Test")
    main.set_current_project(pid)

    spec_ctrl = SpectrumController(main)
    color_ctrl = ColorController(main)
    page = AnalyzePage(spec_ctrl, color_ctrl)
    qtbot.addWidget(page)
    yield page
    main.shutdown()


@pytest.fixture
def optimize_page(tmp_path: Path, qtbot):
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    proj_ctrl = ProjectController(main)
    pid = proj_ctrl.create_project("Test")
    main.set_current_project(pid)

    opt_ctrl = OptimizationController(main)
    page = OptimizePage(opt_ctrl)
    qtbot.addWidget(page)
    yield page
    main.shutdown()


class TestAnalyzePage:
    def test_page_creation(self, analyze_page: AnalyzePage) -> None:
        assert not analyze_page._analyze_btn.isEnabled()

    def test_set_target_enables_button(self, analyze_page: AnalyzePage) -> None:
        analyze_page._view_model.set_target(_make_spec(550.0))
        assert analyze_page._analyze_btn.isEnabled()


class TestOptimizePage:
    def test_page_creation(self, optimize_page: OptimizePage) -> None:
        assert optimize_page._wp_btn is not None
        assert optimize_page._th_btn is not None

    def test_white_point_optimization(self, optimize_page: OptimizePage, qtbot) -> None:
        vm = optimize_page._view_model
        red = _make_spec(620.0)
        green = _make_spec(520.0)
        blue = _make_spec(460.0)
        target = XY(x=0.3127, y=0.3290)
        with qtbot.waitSignal(vm.white_point_changed, timeout=1000):
            result = vm.optimize_white_point([red, green, blue], target)
        assert result is not None
        assert len(result.weights) == 3

    def test_thickness_optimization(self, optimize_page: OptimizePage, qtbot) -> None:
        vm = optimize_page._view_model
        source = _make_spec(550.0)
        a1 = _make_spec(600.0)
        a2 = _make_spec(500.0)
        target = XY(x=0.3, y=0.3)
        with qtbot.waitSignal(vm.thickness_changed, timeout=1000):
            result = vm.optimize_thickness(target, source, [a1, a2])
        assert result is not None
        assert len(result.thicknesses_um) == 2
