"""ProjectViewModel — data model for the Project page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from colorlab_pro.controllers.project_controller import ProjectController, ProjectInfo
from colorlab_pro.ui.viewmodels.base import ViewModel


class ProjectViewModel(ViewModel):
    """ViewModel for project list and selection state."""

    # Emitted when the project list has been refreshed.
    project_list_changed = Signal()

    # Emitted when the selected project changes (carries ProjectInfo or None).
    selection_changed = Signal(object)

    def __init__(
        self,
        controller: ProjectController,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with a ProjectController reference.

        Args:
            controller: The project controller for CRUD operations.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._projects: list[ProjectInfo] = []
        self._selected: ProjectInfo | None = None

        # Connect controller signals
        self._controller.projects_updated.connect(self.refresh)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def projects(self) -> list[ProjectInfo]:
        """Return the cached project list."""
        return self._projects

    @property
    def selected_project(self) -> ProjectInfo | None:
        """Return the currently selected project."""
        return self._selected

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Reload the project list from the controller."""
        self._projects = self._controller.list_projects()
        self.project_list_changed.emit()
        self.data_changed.emit()

    def select_project(self, project_id: int | None) -> None:
        """Select a project by id and update state."""
        if project_id is None:
            self._selected = None
            self._controller.select_project(None)
        else:
            info = self._controller.get_project(project_id)
            if info is None:
                self.set_error(f"Project {project_id} not found.")
                return
            self._selected = info
            self._controller.select_project(project_id)
        self.selection_changed.emit(self._selected)

    def create_project(self, name: str, description: str | None = None) -> int | None:
        """Create a new project via the controller."""
        pid = self._controller.create_project(name, description=description)
        if pid is not None:
            self.set_status(f"Project '{name}' created.")
        return pid

    def delete_project(self, project_id: int) -> bool:
        """Delete a project via the controller."""
        result = self._controller.delete_project(project_id)
        if result and self._selected is not None and self._selected.id == project_id:
            self._selected = None
            self.selection_changed.emit(None)
        return result

    def update_project(
        self,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> bool:
        """Update a project via the controller."""
        return self._controller.update_project(project_id, name=name, description=description)
