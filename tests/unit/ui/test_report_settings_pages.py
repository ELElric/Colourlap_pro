"""Tests for ReportPage and SettingsPage."""

from __future__ import annotations

from pathlib import Path

import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.ui.pages.report_page import ReportPage
from colorlab_pro.ui.pages.settings_page import SettingsPage


@pytest.fixture
def report_page(tmp_path: Path, qtbot):
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    page = ReportPage(main)
    qtbot.addWidget(page)
    yield page
    main.shutdown()


@pytest.fixture
def settings_page(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)
    return page


class TestReportPage:
    def test_page_creation(self, report_page: ReportPage) -> None:
        assert report_page._csv_btn is not None
        assert report_page._json_btn is not None

    def test_export_csv_no_window_crash(self, report_page: ReportPage) -> None:
        report_page._main._window = None
        report_page._on_export_csv()  # Should not crash


class TestSettingsPage:
    def test_page_creation(self, settings_page: SettingsPage) -> None:
        assert settings_page._open_btn is not None

    def test_open_settings_dialog(self, settings_page: SettingsPage, qtbot) -> None:
        from unittest.mock import patch

        with patch("colorlab_pro.ui.pages.settings_page.SettingsDialog") as mock_dlg:
            settings_page._open_btn.click()
            mock_dlg.assert_called_once()
