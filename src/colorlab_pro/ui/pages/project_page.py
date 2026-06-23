"""ProjectPage — workspace page for project management."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.project_controller import ProjectController, ProjectInfo
from colorlab_pro.ui.dialogs.new_project_dialog import NewProjectDialog
from colorlab_pro.ui.viewmodels.project_viewmodel import ProjectViewModel


class ProjectPage(QWidget):
    """Workspace page showing project list with CRUD actions."""

    def __init__(
        self,
        controller: ProjectController,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize with a ProjectController.

        Args:
            controller: The project controller for data operations.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._view_model = ProjectViewModel(controller, parent=self)
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        """Construct the page layout."""
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Projects</h3>"))
        header.addStretch()

        self._new_btn = QPushButton("New Project")
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        header.addWidget(self._new_btn)
        header.addWidget(self._delete_btn)
        layout.addLayout(header)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Name", "Description", "Created", "Spectra"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self._table)

        # Status
        self._status_label = QLabel("No project selected.")
        layout.addWidget(self._status_label)

    def _wire_signals(self) -> None:
        """Connect UI signals to ViewModel actions."""
        self._new_btn.clicked.connect(self._on_new_project)
        self._delete_btn.clicked.connect(self._on_delete)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._view_model.project_list_changed.connect(self._refresh_table)
        self._view_model.selection_changed.connect(self._on_selection_changed_vm)
        self._view_model.error_occurred.connect(
            lambda msg: self._status_label.setText(f"Error: {msg}")
        )
        self._view_model.status_changed.connect(lambda msg: self._status_label.setText(msg))

    def connect_auto_refresh(self, window) -> None:
        """Connect to MainWindow.page_about_to_show for auto-refresh on page switch."""
        window.page_about_to_show.connect(self._on_page_show)

    def _on_page_show(self, page_index: int) -> None:
        """Auto-refresh when this page becomes visible."""
        # Project page is always index 0
        if page_index == 0:
            self.refresh()

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #

    def _on_new_project(self) -> None:
        """Open the NewProjectDialog."""
        dlg = NewProjectDialog(self)
        dlg.project_accepted.connect(self._view_model.create_project)
        dlg.open()

    def _selected_project_ids(self) -> list[int]:
        """Return the ids of all selected table rows."""
        ids: list[int] = []
        for idx in self._table.selectionModel().selectedRows():
            item = self._table.item(idx.row(), 0)
            if item is not None:
                pid = item.data(Qt.ItemDataRole.UserRole)
                if pid is not None:
                    ids.append(pid)
        return ids

    def _on_delete(self) -> None:
        """Delete all selected projects after confirmation."""
        ids = self._selected_project_ids()
        if not ids:
            return
        names = [self._view_model._controller.get_project(pid).name for pid in ids]
        reply = QMessageBox.warning(
            self,
            "Delete Project" if len(ids) == 1 else "Delete Projects",
            f"Are you sure you want to delete {', '.join(names)}?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for pid in ids:
                self._view_model.delete_project(pid)

    def _on_rename(self) -> None:
        """Rename the first selected project."""
        ids = self._selected_project_ids()
        if not ids:
            return
        pid = ids[0]
        info = self._view_model._controller.get_project(pid)
        if info is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Project", "Project name:", text=info.name)
        if ok and name.strip():
            self._view_model.update_project(pid, name=name.strip())
            self.refresh()

    def _on_context_menu(self, pos) -> None:
        """Show a context menu for the selected project row(s)."""
        if not self._table.selectionModel().selectedRows():
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == rename_action:
            self._on_rename()
        elif action == delete_action:
            self._on_delete()

    def _on_selection_changed(self) -> None:
        """Handle table row selection."""
        rows = self._table.selectionModel().selectedRows()
        self._delete_btn.setEnabled(bool(rows))
        if rows:
            row = rows[0].row()
            item = self._table.item(row, 0)
            if item is not None:
                pid = item.data(Qt.ItemDataRole.UserRole)
                self._view_model.select_project(pid)

    def _on_selection_changed_vm(self, info: ProjectInfo | None) -> None:
        """Update UI when ViewModel selection changes."""
        self._delete_btn.setEnabled(info is not None)
        if info is not None:
            self._status_label.setText(f"Selected: {info.name} (id={info.id})")
        else:
            self._status_label.setText("No project selected.")

    def _refresh_table(self) -> None:
        """Populate the table from ViewModel data."""
        projects = self._view_model.projects
        self._table.setRowCount(len(projects))
        for row, p in enumerate(projects):
            name_item = QTableWidgetItem(p.name)
            name_item.setData(Qt.ItemDataRole.UserRole, p.id)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(p.description or ""))
            self._table.setItem(row, 2, QTableWidgetItem(p.created_at[:10]))
            self._table.setItem(row, 3, QTableWidgetItem(str(p.spectrum_count)))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Trigger a data refresh."""
        self._view_model.refresh()
