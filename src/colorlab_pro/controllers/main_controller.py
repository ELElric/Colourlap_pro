"""MainController — application-level coordinator for ColorLab Pro.

Owns the database lifecycle, service instantiation, menu actions,
and coordinates page switching between workspace controllers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from colorlab_pro.services.color_service import ColorService
from colorlab_pro.services.database_service import DatabaseService
from colorlab_pro.services.gamut_service import GamutService
from colorlab_pro.services.optimization_service import OptimizationService
from colorlab_pro.services.spectrum_service import SpectrumService
from colorlab_pro.ui.dialogs.about_dialog import AboutDialog
from colorlab_pro.ui.main_window import MainWindow
from colorlab_pro.utils.paths import ensure_data_directory, get_default_db_path


class MainController(QObject):
    """Central coordinator: database, services, menus, page routing."""

    # Emitted when the active project changes (project_id or None).
    project_changed = Signal(object)

    # Emitted when a status message should be shown.
    status_message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the controller without opening the window."""
        super().__init__(parent)
        self._window: MainWindow | None = None
        self._engine = None
        self._session_factory: Callable[[], Session] | None = None

        # Services (initialized after DB setup)
        self.spectrum_service: SpectrumService | None = None
        self.color_service: ColorService | None = None
        self.gamut_service: GamutService | None = None
        self.optimization_service: OptimizationService | None = None

        # Sub-controllers (registered later)
        self._page_controllers: dict[int, QObject] = {}

        # Runtime state
        self._current_project_id: int | None = None

    @property
    def session_factory(self) -> Callable[[], Session] | None:
        """Return the session factory, or None if database is not initialized."""
        return self._session_factory

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def initialize(self, db_path: Path | None = None) -> None:
        """Create engine, tables, session factory, and services.

        Args:
            db_path: Override the default SQLite database path.
        """
        target_db = db_path or get_default_db_path()
        ensure_data_directory()

        self._engine = create_engine(f"sqlite:///{target_db}", echo=False)
        db_service = DatabaseService(self._engine)
        db_service.initialize(db_path=target_db)

        factory = sessionmaker(bind=self._engine)
        self._session_factory = factory

        # Instantiate services
        self.spectrum_service = SpectrumService(factory)
        self.color_service = ColorService(factory)
        self.gamut_service = GamutService()
        self.optimization_service = OptimizationService(factory)

        # Restore last used project
        self._restore_last_project()

        self.status_message.emit("Database initialized.")

    def shutdown(self) -> None:
        """Dispose of the database engine."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    # ------------------------------------------------------------------ #
    # Window
    # ------------------------------------------------------------------ #

    def create_window(self) -> MainWindow:
        """Factory: create the main window."""
        self._window = MainWindow()
        return self._window

    def show_window(self) -> None:
        """Show the main window if it exists."""
        if self._window is not None:
            self._window.show()

    @property
    def window(self) -> MainWindow | None:
        """Return the current MainWindow instance."""
        return self._window

    # ------------------------------------------------------------------ #
    # Page / Controller registration
    # ------------------------------------------------------------------ #

    def register_page_controller(self, page_index: int, controller: QObject) -> None:
        """Associate a sub-controller with a workspace page index."""
        self._page_controllers[page_index] = controller

    def switch_to_page(self, index: int) -> None:
        """Switch the main window to the given page index."""
        if self._window is not None:
            self._window.set_page(index)

    # ------------------------------------------------------------------ #
    # Project state
    # ------------------------------------------------------------------ #

    @property
    def current_project_id(self) -> int | None:
        """Return the currently active project id."""
        return self._current_project_id

    def set_current_project(self, project_id: int | None) -> None:
        """Update the active project and notify listeners."""
        self._current_project_id = project_id
        self.project_changed.emit(project_id)
        if project_id is not None:
            self.status_message.emit(f"Project {project_id} selected.")
            self._save_last_project(project_id)
        else:
            self.status_message.emit("No project selected.")

    def _restore_last_project(self) -> None:
        """Restore the last used project from QSettings."""
        from PySide6.QtCore import QSettings

        from colorlab_pro.config.settings import get_config

        settings = QSettings(get_config().org_name, get_config().app_name)
        last_project_id = settings.value("last_project_id")
        if last_project_id is not None:
            try:
                project_id = int(last_project_id)
                # Verify project exists
                with self._session_factory() as session:
                    from colorlab_pro.database.models import Project

                    if session.get(Project, project_id) is not None:
                        self.set_current_project(project_id)
            except (ValueError, TypeError):
                pass

    def _save_last_project(self, project_id: int) -> None:
        """Save the current project id to QSettings."""
        from PySide6.QtCore import QSettings

        from colorlab_pro.config.settings import get_config

        settings = QSettings(get_config().org_name, get_config().app_name)
        settings.setValue("last_project_id", project_id)


