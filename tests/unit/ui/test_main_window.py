"""Unit tests for the main window."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget

from colorlab_pro.ui.main_window import MainWindow, create_application


@pytest.fixture
def window(qtbot):
    create_application([])
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    return win


def test_window_title(window):
    assert window.windowTitle() == "ColorLab Pro"


def test_central_widget_is_stacked(window):
    central = window.centralWidget()
    assert isinstance(central, QStackedWidget)


def test_sidebar_has_four_items(window):
    assert window._sidebar.count() == 4
    items = [window._sidebar.item(i).text() for i in range(4)]
    assert "Spectrum Library" in items
    assert "Gamut Calculator" in items
    assert "White Point" in items
    assert "Thickness Optimizer" in items


def test_menu_bar_has_file_help_and_settings(window):
    menu_bar = window.menuBar()
    titles = [action.text() for action in menu_bar.actions()]
    assert "&File" in titles
    assert "&Help" in titles
    assert "&Settings" in titles


def test_status_bar_ready(window):
    assert window.statusBar().currentMessage() == "Ready"


def test_add_page_and_set_page(window):
    page = QLabel("Test Page")
    idx = window.add_page(page, "Test")
    window.set_page(idx)
    assert window._stack.currentIndex() == idx
    assert window._sidebar.currentRow() == idx


def test_create_application_singleton(qapp):
    app1 = create_application([])
    app2 = create_application([])
    assert app1 is app2
    assert isinstance(app1, QApplication)
