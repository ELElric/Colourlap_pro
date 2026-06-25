"""Default test-data loader for ColorLab Pro.

Preloads the bundled test spectra (BLED, QD Red/Green, CF Red/Green/Blue)
into a default project so the Gamut Calculator is ready for testing on
fresh installs.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from sqlalchemy import select

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.database.models import Project, Spectrum

logger = logger.bind(module=__name__)

# Mapping from file stem -> (display name, channel hint)
DEFAULT_SPECTRA: tuple[tuple[str, str, str], ...] = (
    ("BLED", "BLED", "B"),
    ("QD_Red", "QD_Red", "R"),
    ("QD_Green", "QD_Green", "G"),
    ("CF_Red", "CF_Red", "RCF"),
    ("CF_Green", "CF_Green", "GCF"),
    ("CF_Blue", "CF_Blue", "BCF"),
)

DEFAULT_PROJECT_NAME: str = "Default Demo"
DEFAULT_PROJECT_DESCRIPTION: str = "Preloaded BLED/QD/CF test spectra"


def _find_test_data_dir() -> Path | None:
    """Locate the test_data directory relative to the project root."""
    # When running from src/colorlab_pro/utils/default_data_loader.py
    candidate = Path(__file__).resolve().parents[3] / "test_data"
    if candidate.is_dir():
        logger.debug("Found test_data directory: {}", candidate)
        return candidate

    # Fallback: search upward from cwd for a test_data folder
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "test_data"
        if candidate.is_dir():
            logger.debug("Found test_data directory via cwd fallback: {}", candidate)
            return candidate

    logger.warning("test_data directory not found near {} or {}", Path(__file__), Path.cwd())
    return None


def _get_or_create_default_project(
    main_controller: MainController,
    project_controller: ProjectController,
) -> int | None:
    """Return the default project id, creating it if necessary."""
    session_factory = main_controller.session_factory
    if session_factory is None:
        logger.error("Database session factory not available.")
        return None

    with session_factory() as session:
        project = session.execute(select(Project).filter(Project.name == DEFAULT_PROJECT_NAME)).scalar_one_or_none()
        if project is not None:
            logger.info("Using existing default project (id={}).", project.id)
            return int(project.id)

    logger.info("Creating default project '{}'.", DEFAULT_PROJECT_NAME)
    # Create via controller so signals/state are updated consistently.
    project_id = project_controller.create_project(
        DEFAULT_PROJECT_NAME, description=DEFAULT_PROJECT_DESCRIPTION
    )
    if project_id is None:
        logger.error("Failed to create default project.")
    else:
        logger.info("Created default project (id={}).", project_id)
    return project_id


def _existing_spectrum_names(session_factory, project_id: int) -> set[str]:
    """Return the lower-cased names of spectra already in the project."""
    with session_factory() as session:
        spectra = session.execute(select(Spectrum.name).filter(Spectrum.project_id == project_id)).scalars().all()
        return {str(name).lower() for name in spectra if name}


def _all_spectrum_ids(session_factory, project_id: int) -> list[int]:
    """Return all spectrum ids in the default project."""
    with session_factory() as session:
        ids = session.execute(
            select(Spectrum.id)
            .filter(Spectrum.project_id == project_id)
            .order_by(Spectrum.id)
        ).scalars().all()
        return [int(sid) for sid in ids]


def load_default_spectra(main_controller: MainController) -> list[int]:
    """Import the bundled test spectra into the default project.

    Idempotent: spectra that already exist in the default project (by name)
    are skipped.

    Returns:
        List of all spectrum ids in the default project after loading.
    """
    project_controller = ProjectController(main_controller)
    spectrum_controller = SpectrumController(main_controller)

    spectrum_controller.error_occurred.connect(
        lambda msg: logger.error("Spectrum import error: {}", msg)
    )

    project_id = _get_or_create_default_project(main_controller, project_controller)
    if project_id is None:
        main_controller.status_message.emit("Failed to initialize default project.")
        return []

    main_controller.set_current_project(project_id)

    session_factory = main_controller.session_factory
    if session_factory is None:
        return []

    test_data_dir = _find_test_data_dir()
    if test_data_dir is None:
        logger.info("Test data directory not found; default project created without spectra.")
        main_controller.status_message.emit("Default project ready (no test data loaded).")
        return _all_spectrum_ids(session_factory, project_id)

    existing = _existing_spectrum_names(session_factory, project_id)
    imported_count = 0

    for stem, name, channel in DEFAULT_SPECTRA:
        if name.lower() in existing:
            logger.info("Spectrum '{}' already exists, skipping.", name)
            continue

        csv_path = test_data_dir / f"{stem}.csv"
        if not csv_path.exists():
            logger.warning("Default spectrum file not found: {}", csv_path)
            continue

        logger.info("Importing default spectrum '{}' from '{}'.", name, csv_path)
        spectrum_id = spectrum_controller.import_csv_file(
            csv_path,
            name=name,
            channel=channel,
        )
        if spectrum_id is not None:
            imported_count += 1
            logger.info("Imported '{}' (id={}).", name, spectrum_id)
        else:
            logger.error("Failed to import '{}'.", name)

    all_ids = _all_spectrum_ids(session_factory, project_id)
    total = len(all_ids)
    msg = f"Default project ready: {imported_count} imported, {total} total spectra."
    logger.info(msg)
    main_controller.status_message.emit(msg)
    return all_ids
