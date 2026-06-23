"""Unit tests for ViewModel base class."""

from __future__ import annotations

from colorlab_pro.ui.viewmodels.base import ViewModel


def test_error_signal(qtbot):
    vm = ViewModel()
    with qtbot.waitSignal(vm.error_occurred, timeout=1000):
        vm.set_error("Something went wrong")


def test_status_signal(qtbot):
    vm = ViewModel()
    with qtbot.waitSignal(vm.status_changed, timeout=1000):
        vm.set_status("Ready")


def test_data_changed_signal(qtbot):
    vm = ViewModel()
    with qtbot.waitSignal(vm.data_changed, timeout=1000):
        vm.data_changed.emit()
