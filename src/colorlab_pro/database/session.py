"""SQLAlchemy session factory and engine creation.

Includes a lightweight schema-version migration system with automatic
pre-migration backups so user data is never lost when the schema evolves.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import Base

SessionMaker = sessionmaker

# Bump this when a new migration step is added to ``_MIGRATIONS``.
CURRENT_SCHEMA_VERSION = 4

# Name of the metadata table that records the applied schema version.
_VERSION_TABLE = "schema_version"


def create_engine_from_path(db_path: Path) -> Engine:
    """Create a SQLAlchemy engine for an SQLite database path.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLAlchemy Engine.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def _backup_database(db_path: Path, version: int) -> Path | None:
    """Copy ``db_path`` to ``db_path.bak.v{version}`` before migrating.

    Returns the backup path, or ``None`` if the source does not exist yet
    (e.g. first-time creation).
    """
    if not db_path.exists():
        return None
    backup = db_path.with_suffix(f"{db_path.suffix}.bak.v{version}")
    shutil.copy2(db_path, backup)
    return backup


def _ensure_version_table(engine: Engine) -> int:
    """Create the version table if missing and return the current version.

    Returns 0 when the database predates the version-table mechanism (i.e.
    an existing database created by ColorLab Pro <= 1.1.0 that has tables
    but no ``schema_version`` table yet).
    """
    inspector = inspect(engine)
    if _VERSION_TABLE not in inspector.get_table_names():
        # Determine baseline version.
        if inspector.get_table_names():
            # Pre-existing database without version tracking. Treat as v1
            # so that v1→v2 migrations (e.g. category column) are applied.
            baseline = 1
        else:
            # Fresh database — no migrations needed yet.
            baseline = CURRENT_SCHEMA_VERSION
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE TABLE {_VERSION_TABLE} ("
                    "  version INTEGER NOT NULL,"
                    "  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.execute(text(f"INSERT INTO {_VERSION_TABLE} (version) VALUES ({baseline})"))
        return baseline

    with engine.begin() as conn:
        result = conn.execute(text(f"SELECT MAX(version) FROM {_VERSION_TABLE}"))
        row = result.scalar()
        return int(row) if row is not None else 0


def _migration_v1_to_v2(engine: Engine) -> None:
    """v1 → v2: add ``category`` column to ``spectra`` if missing.

    This was previously a standalone ``_migrate_schema`` check; it is now a
    numbered migration step so the version table tracks whether it has been
    applied.
    """
    inspector = inspect(engine)
    if "spectra" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("spectra")}
    if "category" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE spectra ADD COLUMN category VARCHAR(50)"))


def _migration_v2_to_v3(engine: Engine) -> None:
    """v2 → v3: add ``fwhm``, ``peak_wavelength`` to ``spectra`` and
    ``created_at`` to ``optimizations`` if missing.

    These columns support pre-computed FWHM/peak at import time and
    optimization history tracking.
    """
    inspector = inspect(engine)

    if "spectra" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("spectra")}
        if "fwhm" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE spectra ADD COLUMN fwhm FLOAT"))
        if "peak_wavelength" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE spectra ADD COLUMN peak_wavelength FLOAT"))

    if "optimizations" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("optimizations")}
        if "created_at" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE optimizations ADD COLUMN created_at TIMESTAMP")
                )


def _migration_v3_to_v4(engine: Engine) -> None:
    """v3 → v4: add chromaticity columns to ``spectra`` if missing.

    Adds ``xy_x``, ``xy_y``, ``uv_u``, ``uv_v``, ``dominant_wavelength``,
    ``purity`` — pre-computed CIE 1931 xy and 1976 u'v' chromaticity
    coordinates stored at import time.
    """
    inspector = inspect(engine)
    if "spectra" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("spectra")}
    for col_name in ("xy_x", "xy_y", "uv_u", "uv_v", "dominant_wavelength", "purity"):
        if col_name not in columns:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE spectra ADD COLUMN {col_name} FLOAT"))


# Ordered list of migrations; ``_MIGRATIONS[i]`` upgrades from version
# ``i+1`` to version ``i+2``.
_MIGRATIONS = [
    _migration_v1_to_v2,  # v1 → v2
    _migration_v2_to_v3,  # v2 → v3
    _migration_v3_to_v4,  # v3 → v4
]


def _migrate_schema(engine: Engine, db_path: Path | None = None) -> int:
    """Apply pending schema migrations and return the new version.

    A backup of the database file is taken before the first migration is
    applied (when ``db_path`` is provided and the file exists).
    """
    version = _ensure_version_table(engine)

    if version >= CURRENT_SCHEMA_VERSION:
        return version

    # We have pending migrations. Back up the database file before proceeding
    # so user data can be recovered if a migration fails.
    backed_up = False
    while version < CURRENT_SCHEMA_VERSION:
        idx = version - 1  # _MIGRATIONS[0] is v1→v2
        if idx < 0 or idx >= len(_MIGRATIONS):
            break

        if not backed_up and db_path is not None:
            _backup_database(db_path, version + 1)
            backed_up = True

        migration_fn = _MIGRATIONS[idx]
        migration_fn(engine)

        version += 1
        with engine.begin() as conn:
            conn.execute(text(f"INSERT INTO {_VERSION_TABLE} (version) VALUES ({version})"))

    return version


def init_schema(engine: Engine, db_path: Path | None = None) -> int:
    """Create all tables defined in models.py and apply migrations.

    For brand-new databases (no existing tables) the version table is seeded
    directly to ``CURRENT_SCHEMA_VERSION`` so no migrations or backups are
    triggered. For pre-existing databases, pending migrations are applied
    with a pre-migration backup.

    Args:
        engine: SQLAlchemy engine bound to the target database.
        db_path: Optional path to the database file, used for pre-migration
            backups. When omitted, no backup is taken (useful for in-memory
            or temporary test databases).

    Returns:
        The applied schema version.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if not existing_tables:
        # Fresh database: create tables then seed version table at current.
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE TABLE {_VERSION_TABLE} ("
                    "  version INTEGER NOT NULL,"
                    "  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.execute(
                text(f"INSERT INTO {_VERSION_TABLE} (version) VALUES ({CURRENT_SCHEMA_VERSION})")
            )
        return CURRENT_SCHEMA_VERSION

    # Pre-existing database: create any missing tables then migrate.
    Base.metadata.create_all(engine)
    return _migrate_schema(engine, db_path)


def get_session_maker(engine: Engine) -> sessionmaker:
    """Return a sessionmaker bound to the engine."""
    return sessionmaker(bind=engine, future=True)
