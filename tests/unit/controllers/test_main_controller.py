"""Tests for MainController."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QObject

from colorlab_pro.controllers.main_controller import MainController


@pytest.fixture
def controller(tmp_path: Path, qtbot):
    """Provide a MainController with an in-memory database."""
    ctrl = MainController()
    db_path = tmp_path / "test.db"
    ctrl.initialize(db_path=db_path)
    qtbot.addWidget(ctrl.create_window())
    yield ctrl
    ctrl.shutdown()


class TestLifecycle:
    def test_initialize_creates_services(self, controller: MainController) -> None:
        assert controller.spectrum_service is not None
        assert controller.color_service is not None
        assert controller.gamut_service is not None
        assert controller.optimization_service is not None

    def test_initialize_emits_status(self, controller: MainController, qtbot) -> None:
        with qtbot.waitSignal(controller.status_message, timeout=1000):
            controller.initialize(db_path=Path("/tmp/test2.db"))

    def test_shutdown_disposes_engine(self, controller: MainController) -> None:
        controller.shutdown()
        assert controller._engine is None


class TestProjectState:
    def test_default_project_is_none(self, controller: MainController) -> None:
        assert controller.current_project_id is None

    def test_set_current_project_emits_signal(self, controller: MainController, qtbot) -> None:
        with qtbot.waitSignal(controller.project_changed, timeout=1000):
            controller.set_current_project(42)
        assert controller.current_project_id == 42

    def test_set_current_project_to_none(self, controller: MainController) -> None:
        controller.set_current_project(1)
        controller.set_current_project(None)
        assert controller.current_project_id is None


class TestWindow:
    def test_create_window_returns_main_window(self, controller: MainController) -> None:
        assert controller.window is not None
        assert controller.window.windowTitle() == "ColorLab Pro"

    def test_show_window_does_not_crash(self, controller: MainController) -> None:
        controller.show_window()


class TestPageRegistration:
    def test_register_and_switch_page(self, controller: MainController) -> None:
        mock_ctrl = QObject()
        controller.register_page_controller(0, mock_ctrl)
        assert controller._page_controllers[0] is mock_ctrl
        controller.switch_to_page(0)


class TestMenuActions:
    def test_about_does_not_crash(self, controller: MainController) -> None:
        with patch("colorlab_pro.controllers.main_controller.AboutDialog"):
            controller._on_about()

    def test_new_project_does_not_crash(self, controller: MainController) -> None:
        with patch("colorlab_pro.controllers.main_controller.NewProjectDialog"):
            controller._on_new_project()

    def test_open_project_does_not_crash(self, controller: MainController) -> None:
        with patch("colorlab_pro.controllers.main_controller.QMessageBox.information"):
            controller._on_open_project()


class TestExportHelper:
    def test_prompt_export_path_returns_none_when_window_none(
        self, controller: MainController
    ) -> None:
        controller._window = None
        result = controller.prompt_export_path("Save", "CSV (*.csv)")
        assert result is None

    def test_prompt_export_path_returns_selected_path(
        self, controller: MainController, qtbot
    ) -> None:
        with patch(
            "colorlab_pro.controllers.main_controller.QFileDialog.getSaveFileName",
            return_value=("C:/tmp/export.csv", "CSV (*.csv)"),
        ):
            result = controller.prompt_export_path("Save", "CSV (*.csv)")
        assert result == Path("C:/tmp/export.csv")


class TestMenuInternals:
    def test_wire_menu_actions_with_no_window(self, controller: MainController) -> None:
        controller._window = None
        controller._wire_menu_actions()

    def test_find_action_with_no_window(self, controller: MainController) -> None:
        controller._window = None
        assert controller._find_action("&About") is None

    def test_on_new_project_with_no_window(self, controller: MainController) -> None:
        controller._window = None
        controller._on_new_project()

    def test_on_about_with_no_window(self, controller: MainController) -> None:
        controller._window = None
        controller._on_about()

    def test_create_project_from_dialog(self, controller: MainController, qtbot) -> None:
        with qtbot.waitSignal(controller.status_message, timeout=1000):
            controller._create_project_from_dialog("Dialog Project", "desc")
        assert controller.current_project_id is not None
