"""ProjectController — manages project CRUD and selection state.

Mediates between the Project page UI and ProjectRepository.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from sqlalchemy.orm import Session

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.repositories import project_repository


@dataclass(frozen=True)
class ProjectInfo:
    """Lightweight DTO for UI project lists."""

    id: int
    name: str
    description: str | None
    created_at: str
    updated_at: str
    spectrum_count: int

    @classmethod
    def from_dict(cls, data: dict) -> ProjectInfo:
        """Build a ProjectInfo from a dictionary."""
        return cls(
            id=int(data["id"]),
            name=data["name"],
            description=data.get("description"),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            spectrum_count=int(data.get("spectrum_count", 0)),
        )


class ProjectController(QObject):
    """Controller for project lifecycle operations."""

    # Emitted when the project list changes.
    projects_updated = Signal()

    # Emitted when a single project is created (carries its id).
    project_created = Signal(int)

    # Emitted when a project is deleted (carries its id).
    project_deleted = Signal(int)

    # Emitted on operation errors.
    error_occurred = Signal(str)

    def __init__(
        self,
        main_controller: MainController,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with a reference to MainController for DB access.

        Args:
            main_controller: The application-level coordinator.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._main = main_controller

    # ------------------------------------------------------------------ #
    # Internal helper
    # ------------------------------------------------------------------ #

    def _session_factory(self) -> Callable[[], Session]:
        """Return the session factory from MainController."""
        if self._main._session_factory is None:
            raise RuntimeError("Database not initialized.")
        return self._main._session_factory

    # ------------------------------------------------------------------ #
    # CRUD operations
    # ------------------------------------------------------------------ #

    def create_project(self, name: str, description: str | None = None) -> int | None:
        """Create a new project and return its id.

        Args:
            name: Project display name.
            description: Optional description.

        Returns:
            The new project id, or None on error.
        """
        if not name or not name.strip():
            self.error_occurred.emit("Project name cannot be empty.")
            return None

        try:
            with self._session_factory()() as session:
                project = project_repository.create(
                    session, name=name.strip(), description=description
                )
                session.commit()
                project_id = int(project.id)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to create project: {exc}")
            return None

        self.projects_updated.emit()
        self.project_created.emit(project_id)
        self._main.set_current_project(project_id)
        return project_id

    def list_projects(self) -> list[ProjectInfo]:
        """Return all projects as lightweight DTOs."""
        try:
            with self._session_factory()() as session:
                projects = project_repository.list_all(session)
                return [
                    ProjectInfo.from_dict(
                        {
                            "id": p.id,
                            "name": p.name,
                            "description": p.description,
                            "created_at": p.created_at.isoformat(),
                            "updated_at": p.updated_at.isoformat(),
                            "spectrum_count": len(p.spectra),
                        }
                    )
                    for p in projects
                ]
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to list projects: {exc}")
            return []

    def get_project(self, project_id: int) -> ProjectInfo | None:
        """Load a single project by id."""
        try:
            with self._session_factory()() as session:
                project = project_repository.get_by_id(session, project_id)
                if project is None:
                    return None
                return ProjectInfo.from_dict(
                    {
                        "id": project.id,
                        "name": project.name,
                        "description": project.description,
                        "created_at": project.created_at.isoformat(),
                        "updated_at": project.updated_at.isoformat(),
                        "spectrum_count": len(project.spectra),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to get project: {exc}")
            return None

    def update_project(
        self,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> bool:
        """Update a project's fields.

        Returns True if the project existed and was updated.
        """
        try:
            with self._session_factory()() as session:
                project = project_repository.update(
                    session, project_id, name=name, description=description
                )
                if project is None:
                    self.error_occurred.emit(f"Project {project_id} not found.")
                    return False
                session.commit()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to update project: {exc}")
            return False

        self.projects_updated.emit()
        return True

    def delete_project(self, project_id: int) -> bool:
        """Delete a project and its cascaded data.

        Returns True if the project existed and was deleted.
        """
        try:
            with self._session_factory()() as session:
                result = project_repository.delete(session, project_id)
                if not result:
                    self.error_occurred.emit(f"Project {project_id} not found.")
                    return False
                session.commit()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to delete project: {exc}")
            return False

        # If the deleted project was the current one, clear selection
        if self._main.current_project_id == project_id:
            self._main.set_current_project(None)

        self.projects_updated.emit()
        self.project_deleted.emit(project_id)
        return True

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    def select_project(self, project_id: int | None) -> None:
        """Set the active project in MainController."""
        if project_id is not None:
            info = self.get_project(project_id)
            if info is None:
                self.error_occurred.emit(f"Project {project_id} not found.")
                return
        self._main.set_current_project(project_id)
