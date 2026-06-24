"""Unit tests for the main window."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QStackedWidget, QWidget

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
    assert isinstance(central, QWidget)
    # central widget is a composite container, not the stack directly
    assert hasattr(window, "_stack")
    assert isinstance(window._stack, QStackedWidget)


def test_sidebar_has_four_items(window):
    buttons = window._sidebar.findChildren(QPushButton)
    assert len(buttons) == 4
    items = [btn.text() for btn in buttons]
    assert any("Spectrum Library" in t for t in items)
    assert any("Gamut Calculator" in t for t in items)
    assert any("White Point" in t for t in items)
    assert any("Thickness Optimizer" in t for t in items)


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


def test_create_application_singleton(qapp):
    app1 = create_application([])
    app2 = create_application([])
    assert app1 is app2
    assert isinstance(app1, QApplication)
