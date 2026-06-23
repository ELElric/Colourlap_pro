"""DatabaseService handles database lifecycle operations."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine

from colorlab_pro.database.session import init_schema


class DatabaseService:
    """Service for database initialization and lifecycle."""

    def __init__(self, engine: Engine) -> None:
        """Initialize with a SQLAlchemy engine.

        Args:
            engine: SQLAlchemy engine instance.
        """
        self._engine = engine

    def initialize(self, db_path: Path | None = None) -> None:
        """Create all tables and apply migrations.

        Args:
            db_path: Optional path to the database file, used for
                pre-migration backups.
        """
        init_schema(self._engine, db_path)
