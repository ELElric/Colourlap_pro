"""Unit tests for SQLAlchemy ORM models (T-07)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import (
    Base,
    Optimization,
    Project,
    Spectrum,
    SpectrumPoint,
)


@pytest.fixture
def engine(tmp_path_factory: pytest.TempPathFactory) -> object:
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    return create_engine(f"sqlite:///{db_path}", future=True)


@pytest.fixture
def session(engine: object) -> object:
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine, future=True)
    with session_maker() as s:
        yield s


class TestProject:
    def test_create_project(self, session: object) -> None:
        p = Project(name="Test Project", description="desc")
        session.add(p)
        session.commit()
        assert p.id is not None
        assert p.name == "Test Project"

    def test_project_has_spectra(self, session: object) -> None:
        p = Project(name="P1")
        session.add(p)
        session.commit()
        spec = Spectrum(
            project_id=p.id,
            name="R",
            unit="a.u.",
            source="import",
            point_count=401,
        )
        session.add(spec)
        session.commit()
        assert len(p.spectra) == 1
        assert p.spectra[0].name == "R"


class TestSpectrum:
    def test_spectrum_with_points(self, session: object) -> None:
        p = Project(name="P2")
        session.add(p)
        session.commit()
        spec = Spectrum(
            project_id=p.id,
            name="test",
            point_count=3,
        )
        session.add(spec)
        session.commit()
        for i in range(3):
            sp = SpectrumPoint(
                spectrum_id=spec.id,
                idx=i,
                wavelength=380.0 + i,
                value=0.5,
            )
            session.add(sp)
        session.commit()
        assert len(spec.points) == 3
        assert spec.points[0].wavelength == 380.0

    def test_cascade_delete_points(self, session: object) -> None:
        p = Project(name="P3")
        session.add(p)
        session.commit()
        spec = Spectrum(project_id=p.id, name="to-delete")
        session.add(spec)
        session.commit()
        sp = SpectrumPoint(spectrum_id=spec.id, idx=0, wavelength=550.0, value=1.0)
        session.add(sp)
        session.commit()
        session.delete(spec)
        session.commit()
        remaining = session.query(SpectrumPoint).filter(SpectrumPoint.spectrum_id == spec.id).all()
        assert len(remaining) == 0


class TestOptimization:
    def test_create_optimization(self, session: object) -> None:
        p = Project(name="P4")
        session.add(p)
        session.commit()
        opt = Optimization(
            project_id=p.id,
            name="D65 match",
            target_xy_x=0.3127,
            target_xy_y=0.3290,
            result_json='{"thicknesses": [1.0, 1.2, 0.9]}',
        )
        session.add(opt)
        session.commit()
        assert opt.id is not None
        assert opt.project_id == p.id


class TestMigrations:
    def test_all_tables_exist(self, engine: object) -> None:
        Base.metadata.create_all(engine)
        # reflect
        from sqlalchemy import inspect

        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "projects" in tables
        assert "spectra" in tables
        assert "spectrum_points" in tables
        assert "optimizations" in tables
