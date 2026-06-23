"""Tests for ProjectPage and ProjectViewModel."""

from __future__ import annotations

from pathlib import Path

import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.ui.pages.project_page import ProjectPage


@pytest.fixture
def project_page(tmp_path: Path, qtbot):
    """Provide a ProjectPage backed by an in-memory database."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    ctrl = ProjectController(main)
    page = ProjectPage(ctrl)
    qtbot.addWidget(page)
    yield page
    main.shutdown()


class TestProjectViewModel:
    def test_refresh_empty(self, project_page: ProjectPage) -> None:
        vm = project_page._view_model
        vm.refresh()
        assert vm.projects == []

    def test_create_and_refresh(self, project_page: ProjectPage) -> None:
        vm = project_page._view_model
        vm.create_project("Test", "desc")
        vm.refresh()
        assert len(vm.projects) == 1
        assert vm.projects[0].name == "Test"

    def test_select_project(self, project_page: ProjectPage, qtbot) -> None:
        vm = project_page._view_model
        pid = vm.create_project("Selectable")
        with qtbot.waitSignal(vm.selection_changed, timeout=1000):
            vm.select_project(pid)
        assert vm.selected_project is not None
        assert vm.selected_project.name == "Selectable"

    def test_delete_project(self, project_page: ProjectPage) -> None:
        vm = project_page._view_model
        pid = vm.create_project("Deletable")
        vm.delete_project(pid)
        vm.refresh()
        assert len(vm.projects) == 0


class TestProjectPage:
    def test_page_creation(self, project_page: ProjectPage) -> None:
        assert project_page._table.rowCount() == 0
        assert not project_page._delete_btn.isEnabled()

    def test_new_button_opens_dialog(self, project_page: ProjectPage, qtbot) -> None:
        from unittest.mock import patch

        with patch("colorlab_pro.ui.pages.project_page.NewProjectDialog") as mock_dlg:
            project_page._new_btn.click()
            mock_dlg.assert_called_once()

    def test_refresh_populates_table(self, project_page: ProjectPage) -> None:
        vm = project_page._view_model
        vm.create_project("P1")
        vm.create_project("P2")
        project_page.refresh()
        assert project_page._table.rowCount() == 2
