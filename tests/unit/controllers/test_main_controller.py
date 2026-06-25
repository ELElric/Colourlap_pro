"""Tests for MainController."""

from __future__ import annotations

from pathlib import Path

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


