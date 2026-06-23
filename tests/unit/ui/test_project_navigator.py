"""Unit tests for ProjectNavigator."""

from __future__ import annotations

from colorlab_pro.ui.widgets.project_navigator import ProjectNavigator


def test_set_projects_populates_list(qtbot):
    navigator = ProjectNavigator()
    qtbot.addWidget(navigator)
    navigator.set_projects([(1, "Alpha"), (2, "Beta")])
    assert navigator._list.count() == 2


def test_selected_project_id_initially_none(qtbot):
    navigator = ProjectNavigator()
    qtbot.addWidget(navigator)
    assert navigator.selected_project_id() is None


def test_selection_emits_project_id(qtbot):
    navigator = ProjectNavigator()
    qtbot.addWidget(navigator)
    navigator.set_projects([(10, "Demo")])

    received = []
    navigator.project_selected.connect(lambda pid: received.append(pid))
    navigator._list.setCurrentRow(0)

    assert received == [10]


def test_new_project_button_emits_signal(qtbot):
    navigator = ProjectNavigator()
    qtbot.addWidget(navigator)

    received = []
    navigator.new_project_requested.connect(lambda: received.append(True))
    navigator._new_button.click()

    assert len(received) == 1
