"""Tests for ProjectController."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.project_controller import ProjectController, ProjectInfo


@pytest.fixture
def project_ctrl(tmp_path: Path):
    """Provide a ProjectController backed by an in-memory database."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")

    ctrl = ProjectController(main)
    yield ctrl
    main.shutdown()


class TestCreate:
    def test_create_project_returns_id(self, project_ctrl: ProjectController) -> None:
        created_ids: list[int] = []
        project_ctrl.project_created.connect(lambda pid: created_ids.append(pid))
        pid = project_ctrl.create_project("Test Project", "A description")
        assert pid is not None
        assert isinstance(pid, int)
        assert pid in created_ids  # signal emitted

    def test_create_project_sets_current(self, project_ctrl: ProjectController) -> None:
        pid = project_ctrl.create_project("Active")
        assert project_ctrl._main.current_project_id == pid

    def test_create_project_emits_updated(self, project_ctrl: ProjectController) -> None:
        updated_flags: list = []
        project_ctrl.projects_updated.connect(lambda: updated_flags.append(True))
        project_ctrl.create_project("Emit Test")
        assert updated_flags  # signal emitted

    def test_create_project_empty_name_fails(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = project_ctrl.create_project("  ")
        assert result is None
        assert errors


class TestList:
    def test_list_empty(self, project_ctrl: ProjectController) -> None:
        assert project_ctrl.list_projects() == []

    def test_list_after_create(self, project_ctrl: ProjectController) -> None:
        project_ctrl.create_project("P1")
        project_ctrl.create_project("P2")
        projects = project_ctrl.list_projects()
        assert len(projects) == 2
        assert projects[0].name == "P1"
        assert projects[1].name == "P2"


class TestGet:
    def test_get_existing(self, project_ctrl: ProjectController) -> None:
        pid = project_ctrl.create_project("Get Me")
        info = project_ctrl.get_project(pid)
        assert info is not None
        assert info.name == "Get Me"
        assert isinstance(info, ProjectInfo)

    def test_get_missing(self, project_ctrl: ProjectController) -> None:
        assert project_ctrl.get_project(9999) is None


class TestUpdate:
    def test_update_name(self, project_ctrl: ProjectController) -> None:
        pid = project_ctrl.create_project("Old Name")
        result = project_ctrl.update_project(pid, name="New Name")
        assert result is True
        info = project_ctrl.get_project(pid)
        assert info is not None
        assert info.name == "New Name"

    def test_update_missing_project(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = project_ctrl.update_project(9999, name="X")
        assert result is False
        assert errors


class TestDelete:
    def test_delete_existing(self, project_ctrl: ProjectController) -> None:
        pid = project_ctrl.create_project("To Delete")
        deleted_ids: list[int] = []
        project_ctrl.project_deleted.connect(lambda pid: deleted_ids.append(pid))
        result = project_ctrl.delete_project(pid)
        assert result is True
        assert pid in deleted_ids  # signal emitted
        assert project_ctrl.get_project(pid) is None

    def test_delete_clears_current_project(self, project_ctrl: ProjectController) -> None:
        pid = project_ctrl.create_project("Current")
        project_ctrl.delete_project(pid)
        assert project_ctrl._main.current_project_id is None

    def test_delete_missing(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = project_ctrl.delete_project(9999)
        assert result is False
        assert errors


class TestSelect:
    def test_select_project(self, project_ctrl: ProjectController) -> None:
        pid = project_ctrl.create_project("Selectable")
        project_ctrl.select_project(pid)
        assert project_ctrl._main.current_project_id == pid

    def test_select_none(self, project_ctrl: ProjectController) -> None:
        project_ctrl.create_project("X")
        project_ctrl.select_project(None)
        assert project_ctrl._main.current_project_id is None

    def test_select_invalid_emits_error(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        project_ctrl.select_project(9999)
        assert errors


class TestSessionFactory:
    def test_session_factory_uninitialized(self, project_ctrl: ProjectController) -> None:
        project_ctrl._main._session_factory = None
        with pytest.raises(RuntimeError, match="Database not initialized"):
            project_ctrl._session_factory()


class TestRepositoryExceptions:
    def test_create_project_exception(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch(
            "colorlab_pro.controllers.project_controller.project_repository.create",
            side_effect=RuntimeError("db error"),
        ):
            result = project_ctrl.create_project("Fails")
        assert result is None
        assert errors

    def test_list_projects_exception(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch(
            "colorlab_pro.controllers.project_controller.project_repository.list_all",
            side_effect=RuntimeError("db error"),
        ):
            result = project_ctrl.list_projects()
        assert result == []
        assert errors

    def test_get_project_exception(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch(
            "colorlab_pro.controllers.project_controller.project_repository.get_by_id",
            side_effect=RuntimeError("db error"),
        ):
            result = project_ctrl.get_project(1)
        assert result is None
        assert errors

    def test_update_project_exception(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch(
            "colorlab_pro.controllers.project_controller.project_repository.update",
            side_effect=RuntimeError("db error"),
        ):
            result = project_ctrl.update_project(1, name="X")
        assert result is False
        assert errors

    def test_delete_project_exception(self, project_ctrl: ProjectController) -> None:
        errors: list[str] = []
        project_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch(
            "colorlab_pro.controllers.project_controller.project_repository.delete",
            side_effect=RuntimeError("db error"),
        ):
            result = project_ctrl.delete_project(1)
        assert result is False
        assert errors
