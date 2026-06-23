"""Tests for database/session.py."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from colorlab_pro.database.models import Base
from colorlab_pro.database.session import (
    CURRENT_SCHEMA_VERSION,
    create_engine_from_path,
    get_session_maker,
    init_schema,
)


class TestCreateEngineFromPath:
    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "dir" / "test.db"
        assert not db_path.parent.exists()
        engine = create_engine_from_path(db_path)
        try:
            assert db_path.parent.exists()
            assert engine is not None
        finally:
            engine.dispose()

    def test_engine_connects(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        engine = create_engine_from_path(db_path)
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            engine.dispose()


class TestGetSessionMaker:
    def test_returns_bound_sessionmaker(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        try:
            maker = get_session_maker(engine)
            assert maker is not None
            with maker() as session:
                result = session.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            engine.dispose()


class TestInitSchema:
    def test_creates_all_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        engine = create_engine_from_path(db_path)
        try:
            init_schema(engine)
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            assert "projects" in tables
            assert "spectra" in tables
            assert "spectrum_points" in tables
            assert "optimizations" in tables
        finally:
            engine.dispose()

    def test_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        engine = create_engine_from_path(db_path)
        try:
            init_schema(engine)
            init_schema(engine)
            insp = inspect(engine)
            assert "category" in {col["name"] for col in insp.get_columns("spectra")}
        finally:
            engine.dispose()

    def test_migrates_missing_category_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        try:
            Base.metadata.create_all(engine)
            # Simulate an older schema without the category column.
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE spectra DROP COLUMN category"))

            insp_before = inspect(engine)
            assert "category" not in {col["name"] for col in insp_before.get_columns("spectra")}

            init_schema(engine)

            insp_after = inspect(engine)
            assert "category" in {col["name"] for col in insp_after.get_columns("spectra")}
        finally:
            engine.dispose()

    def test_get_session_maker_integration(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        engine = create_engine_from_path(db_path)
        try:
            init_schema(engine)
            maker = get_session_maker(engine)
            with maker() as session:
                from colorlab_pro.database.models import Project

                project = Project(name="Session Test")
                session.add(project)
                session.commit()
                assert project.id is not None
        finally:
            engine.dispose()


class TestSchemaVersioning:
    """Tests for the schema-version migration system (H-02 fix)."""

    def test_fresh_db_gets_current_version(self, tmp_path: Path) -> None:
        db_path = tmp_path / "fresh.db"
        engine = create_engine_from_path(db_path)
        try:
            version = init_schema(engine)
            assert version == CURRENT_SCHEMA_VERSION

            with engine.connect() as conn:
                row = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
            assert int(row) == CURRENT_SCHEMA_VERSION
        finally:
            engine.dispose()

    def test_version_table_created(self, tmp_path: Path) -> None:
        db_path = tmp_path / "v.db"
        engine = create_engine_from_path(db_path)
        try:
            init_schema(engine)
            insp = inspect(engine)
            assert "schema_version" in insp.get_table_names()
        finally:
            engine.dispose()

    def test_legacy_db_without_version_table_migrates(self, tmp_path: Path) -> None:
        """A pre-existing DB (no version table) is treated as v1 and migrated."""
        db_path = tmp_path / "legacy.db"
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        try:
            # Create tables the old way (no version table, no category column).
            Base.metadata.create_all(engine)
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE spectra DROP COLUMN category"))
            # Drop any version table if create_all made one (it shouldn't).
            insp = inspect(engine)
            if "schema_version" in insp.get_table_names():
                with engine.begin() as conn:
                    conn.execute(text("DROP TABLE schema_version"))

            version = init_schema(engine, db_path=db_path)
            assert version == CURRENT_SCHEMA_VERSION
            insp = inspect(engine)
            assert "category" in {col["name"] for col in insp.get_columns("spectra")}
        finally:
            engine.dispose()

    def test_backup_created_before_migration(self, tmp_path: Path) -> None:
        """A backup file is created when migrating a legacy database."""
        db_path = tmp_path / "backup_test.db"
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        try:
            # Simulate a legacy database: tables exist, no version table,
            # no category column.
            Base.metadata.create_all(engine)
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE spectra DROP COLUMN category"))
            insp = inspect(engine)
            if "schema_version" in insp.get_table_names():
                with engine.begin() as conn:
                    conn.execute(text("DROP TABLE schema_version"))

            init_schema(engine, db_path=db_path)

            # A backup should exist.
            backups = list(tmp_path.glob("backup_test.db.bak.v*"))
            assert len(backups) >= 1
        finally:
            engine.dispose()

    def test_no_backup_for_fresh_db(self, tmp_path: Path) -> None:
        """No backup is created when initializing a brand-new database."""
        db_path = tmp_path / "nofresh.db"
        engine = create_engine_from_path(db_path)
        try:
            init_schema(engine, db_path=db_path)
            backups = list(tmp_path.glob("nofresh.db.bak.v*"))
            assert backups == []
        finally:
            engine.dispose()
