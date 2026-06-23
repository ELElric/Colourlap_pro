"""ProjectNavigator widget for selecting and managing projects."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ProjectNavigator(QWidget):
    """Sidebar-like widget that lists projects and emits selection changes."""

    project_selected = Signal(int)
    new_project_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the navigator."""
        super().__init__(parent)
        self._project_ids: dict[str, int] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Create the list and toolbar."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._list = QListWidget(self)
        self._list.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self._list)

        toolbar = QHBoxLayout()
        self._new_button = QPushButton("New Project", self)
        self._new_button.clicked.connect(self.new_project_requested.emit)
        toolbar.addWidget(self._new_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

    def set_projects(self, projects: list[tuple[int, str]]) -> None:
        """Populate the list with project id/name tuples."""
        self._list.clear()
        self._project_ids.clear()
        for project_id, name in projects:
            item = QListWidgetItem(name)
            self._list.addItem(item)
            self._project_ids[name] = project_id

    def selected_project_id(self) -> int | None:
        """Return the id of the currently selected project, or None."""
        item = self._list.currentItem()
        if item is None:
            return None
        return self._project_ids.get(item.text())

    def _on_current_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        """Emit project_selected when the user changes selection."""
        if current is None:
            return
        project_id = self._project_ids.get(current.text())
        if project_id is not None:
            self.project_selected.emit(project_id)
