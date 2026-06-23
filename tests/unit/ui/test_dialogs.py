"""Tests for UI dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from colorlab_pro.ui.dialogs.about_dialog import AboutDialog
from colorlab_pro.ui.dialogs.new_project_dialog import NewProjectDialog
from colorlab_pro.ui.dialogs.settings_dialog import SettingsDialog


class TestNewProjectDialog:
    def test_dialog_creation(self, qtbot) -> None:
        dlg = NewProjectDialog()
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "New Project"

    def test_project_name_property(self, qtbot) -> None:
        dlg = NewProjectDialog()
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("  My Project  ")
        assert dlg.project_name == "My Project"

    def test_project_description_empty(self, qtbot) -> None:
        dlg = NewProjectDialog()
        qtbot.addWidget(dlg)
        assert dlg.project_description is None

    def test_project_description_filled(self, qtbot) -> None:
        dlg = NewProjectDialog()
        qtbot.addWidget(dlg)
        dlg._desc_edit.setPlainText("A test project")
        assert dlg.project_description == "A test project"

    def test_accept_emits_signal(self, qtbot) -> None:
        dlg = NewProjectDialog()
        qtbot.addWidget(dlg)

        results = []
        dlg.project_accepted.connect(lambda n, d: results.append((n, d)))

        dlg._name_edit.setText("Test")
        dlg._on_accept()

        assert dlg.result() == QDialog.DialogCode.Accepted
        assert results == [("Test", None)]

    def test_accept_rejects_empty_name(self, qtbot) -> None:
        dlg = NewProjectDialog()
        qtbot.addWidget(dlg)

        dlg._name_edit.setText("   ")
        dlg._on_accept()

        assert dlg._error_label.text() == "Project name is required."
        assert dlg.result() != QDialog.DialogCode.Accepted


class TestSettingsDialog:
    def test_dialog_creation(self, qtbot) -> None:
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Settings"

    def test_get_settings(self, qtbot) -> None:
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)
        settings = dlg.get_settings()
        assert "db_path" in settings
        assert "theme" in settings
        assert settings["theme"] in ("dark", "light")

    def test_accept_emits_signal(self, qtbot) -> None:
        dlg = SettingsDialog()
        qtbot.addWidget(dlg)

        results = []
        dlg.settings_applied.connect(results.append)

        dlg._on_accept()

        assert dlg.result() == QDialog.DialogCode.Accepted
        assert len(results) == 1
        assert "theme" in results[0]


class TestAboutDialog:
    def test_dialog_creation(self, qtbot) -> None:
        dlg = AboutDialog()
        qtbot.addWidget(dlg)
        assert "ColorLab Pro" in dlg.windowTitle()
        assert dlg.width() == 360
