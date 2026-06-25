"""Tests for UI dialogs."""
from __future__ import annotations

from colorlab_pro.ui.dialogs.about_dialog import AboutDialog


class TestAboutDialog:
    def test_dialog_creation(self, qtbot) -> None:
        dlg = AboutDialog()
        qtbot.addWidget(dlg)
        assert "ColorLab Pro" in dlg.windowTitle()
        assert dlg.width() == 360
