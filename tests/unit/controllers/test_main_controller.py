"""Tests for MainController."""

from __future__ import annotations

from pathlib import Path

import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.utils.signal import QObject


@pytest.fixture
def controller(tmp_path: Path):
    """Provide a MainController with an in-memory database."""
    ctrl = MainController()
    db_path = tmp_path / "test.db"
    ctrl.initialize(db_path=db_path)
    yield ctrl
    ctrl.shutdown()


class TestLifecycle:
    def test_initialize_creates_services(self, controller: MainController) -> None:
        assert controller.spectrum_service is not None
        assert controller.color_service is not None
        assert controller.gamut_service is not None
        assert controller.optimization_service is not None

    def test_initialize_emits_status(self, controller: MainController, tmp_path: Path) -> None:
        messages: list[str] = []
        controller.status_message.connect(lambda msg: messages.append(msg))
        controller.initialize(db_path=tmp_path / "test2.db")
        assert any("Database initialized" in m for m in messages)

    def test_shutdown_disposes_engine(self, controller: MainController) -> None:
        controller.shutdown()
        assert controller._engine is None


class TestProjectState:
    def test_default_project_is_none(self, controller: MainController) -> None:
        assert controller.current_project_id is None

    def test_set_current_project_emits_signal(self, controller: MainController) -> None:
        received: list = []
        controller.project_changed.connect(lambda pid: received.append(pid))
        controller.set_current_project(42)
        assert 42 in received
        assert controller.current_project_id == 42

    def test_set_current_project_to_none(self, controller: MainController) -> None:
        controller.set_current_project(1)
        controller.set_current_project(None)
        assert controller.current_project_id is None


class TestPageRegistration:
    def test_register_and_switch_page(self, controller: MainController) -> None:
        mock_ctrl = QObject()
        controller.register_page_controller(0, mock_ctrl)
        assert controller._page_controllers[0] is mock_ctrl
        controller.switch_to_page(0)
