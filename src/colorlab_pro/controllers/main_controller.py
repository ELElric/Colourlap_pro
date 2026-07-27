"""MainController — application-level coordinator for ColorLab Pro.

Owns the database lifecycle, service instantiation, menu actions,
and coordinates page switching between workspace controllers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from colorlab_pro.utils.signal import QObject, Signal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from colorlab_pro.services.color_service import ColorService
from colorlab_pro.services.database_service import DatabaseService
from colorlab_pro.services.gamut_service import GamutService
from colorlab_pro.services.optimization_service import OptimizationService
from colorlab_pro.services.spectrum_service import SpectrumService
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

        # Seed the user database from the bundled copy if the user DB is
        # missing or completely empty (no spectra).  This ensures a fresh
        # clone on another machine has the preloaded spectra ready to use.
        # Only seeds when using the default DB path, not when tests or
        # callers pass an explicit db_path.
        if db_path is None:
            self._seed_database_if_needed(target_db)

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

    @staticmethod
    def _seed_database_if_needed(target_db: Path) -> None:
        """Copy bundled database to user location if missing or empty.

        The bundled DB lives at ``src/colorlab_pro/data/colorlab.db`` (next
        to the package).  If the user DB at *target_db* does not exist, or
        exists but contains zero spectra, copy the bundled one over so the
        user gets all preloaded data on first run.
        """
        from loguru import logger

        bundled_db = Path(__file__).resolve().parents[1] / "data" / "colorlab.db"
        if not bundled_db.exists():
            return

        needs_seed = False
        if not target_db.exists():
            needs_seed = True
            logger.info("User database not found at {}; seeding from bundled copy.", target_db)
        else:
            # Check whether the existing DB has any spectra at all.
            try:
                from sqlalchemy import create_engine, text

                engine = create_engine(f"sqlite:///{target_db}", echo=False)
                with engine.connect() as conn:
                    count = conn.execute(text("SELECT COUNT(*) FROM spectra")).scalar()
                engine.dispose()
                if int(count) == 0:
                    needs_seed = True
                    logger.info(
                        "User database at {} has 0 spectra; seeding from bundled copy.",
                        target_db,
                    )
            except Exception:  # noqa: BLE001
                pass  # Table may not exist yet; let init_schema handle it.

        if needs_seed:
            import shutil

            target_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(bundled_db), str(target_db))
            logger.info("Seeded database from {}.", bundled_db)

    def shutdown(self) -> None:
        """Dispose of the database engine."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    # ------------------------------------------------------------------ #
    # Page / Controller registration
    # ------------------------------------------------------------------ #

    def register_page_controller(self, page_index: int, controller: QObject) -> None:
        """Associate a sub-controller with a workspace page index."""
        self._page_controllers[page_index] = controller

    def switch_to_page(self, index: int) -> None:
        """Switch the main window to the given page index.

        In the pywebview build, page switching is handled by JavaScript
        in the frontend; this method is a no-op kept for API compatibility.
        """
        pass

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

    # JSON settings file shared with pywebview_api.py
    _SETTINGS_FILE = Path.home() / ".colorlab_pro" / "settings.json"

    def _load_settings(self) -> dict:
        """Load settings from JSON file."""
        try:
            if self._SETTINGS_FILE.exists():
                import json

                return json.loads(self._SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return {}

    def _save_settings(self, data: dict) -> None:
        """Persist settings to JSON file."""
        try:
            import json

            self._SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._SETTINGS_FILE.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    def _restore_last_project(self) -> None:
        """Restore the last used project from JSON settings."""
        settings = self._load_settings()
        last_project_id = settings.get("last_project_id")
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
        """Save the current project id to JSON settings."""
        settings = self._load_settings()
        settings["last_project_id"] = project_id
        self._save_settings(settings)


