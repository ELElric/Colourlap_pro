"""Integration test for full application launch.

Verifies that the app module can initialize all layers
(database, controllers, pages) without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.ui.main_window import MainWindow
from colorlab_pro.ui.pages.gamut_calculator_page import GamutCalculatorPage
from colorlab_pro.ui.pages.spectrum_page import SpectrumPage
from colorlab_pro.ui.pages.thickness_optimizer_page import ThicknessOptimizerPage
from colorlab_pro.ui.pages.white_point_page import WhitePointPage


@pytest.fixture
def app_setup(tmp_path: Path, qtbot):
    """Provide a fully wired application stack."""
    main = MainController()
    main.initialize(db_path=tmp_path / "integration.db")
    window = main.create_window()
    qtbot.addWidget(window)

    # Create controllers
    proj_ctrl = ProjectController(main)
    spec_ctrl = SpectrumController(main)
    color_ctrl = ColorController(main)
    opt_ctrl = OptimizationController(main)

    # Create and register pages
    pages = [
        SpectrumPage(spec_ctrl, page_index=0),
        GamutCalculatorPage(spec_ctrl, color_ctrl, page_index=1),
        WhitePointPage(color_ctrl, page_index=2),
        ThicknessOptimizerPage(spec_ctrl, color_ctrl, opt_ctrl, page_index=3),
    ]
    for page in pages:
        window.add_page(page, page.objectName())

    yield {
        "main": main,
        "window": window,
        "proj_ctrl": proj_ctrl,
        "spec_ctrl": spec_ctrl,
        "color_ctrl": color_ctrl,
        "opt_ctrl": opt_ctrl,
        "pages": pages,
    }

    main.shutdown()


class TestAppLaunch:
    def test_window_created(self, app_setup) -> None:
        assert app_setup["window"] is not None
        assert isinstance(app_setup["window"], MainWindow)

    def test_all_pages_registered(self, app_setup) -> None:
        window = app_setup["window"]
        assert window._stack.count() == 4

    def test_services_initialized(self, app_setup) -> None:
        main = app_setup["main"]
        assert main.spectrum_service is not None
        assert main.color_service is not None
        assert main.gamut_service is not None
        assert main.optimization_service is not None

    def test_project_crud_flow(self, app_setup) -> None:
        proj_ctrl = app_setup["proj_ctrl"]
        pid = proj_ctrl.create_project("Integration Test")
        assert pid is not None

        projects = proj_ctrl.list_projects()
        assert len(projects) == 1
        assert projects[0].name == "Integration Test"

        result = proj_ctrl.delete_project(pid)
        assert result is True
        assert proj_ctrl.list_projects() == []

    def test_page_switching(self, app_setup, qtbot) -> None:
        window = app_setup["window"]
        num_pages = window._stack.count()
        for i in range(num_pages):
            window.set_page(i)
            assert window._stack.currentIndex() == i
