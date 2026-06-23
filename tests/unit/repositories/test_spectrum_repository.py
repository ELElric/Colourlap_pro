"""Unit tests for SpectrumRepository."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import Base, Project
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.repositories import spectrum_repository as repo


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    with session_factory() as s:
        yield s


@pytest.fixture
def project(session):
    p = Project(name="Test Project")
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def sample_spectrum() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([400.0, 500.0, 600.0, 700.0]),
        values=np.array([0.1, 0.5, 0.8, 0.2]),
        unit="mW/nm",
        meta={"name": "Sample Spectrum", "note": "test"},
    )


def test_save_returns_id(session, project, sample_spectrum):
    sid = repo.save(session, sample_spectrum, project.id)
    session.commit()

    assert isinstance(sid, int)
    assert sid > 0


def test_get_by_id_roundtrip(session, project, sample_spectrum):
    sid = repo.save(session, sample_spectrum, project.id, source="import", channel="R")
    session.commit()

    loaded = repo.get_by_id(session, sid)
    assert loaded is not None
    np.testing.assert_array_equal(loaded.wavelengths, sample_spectrum.wavelengths)
    np.testing.assert_array_equal(loaded.values, sample_spectrum.values)
    assert loaded.unit == sample_spectrum.unit
    assert loaded.meta == sample_spectrum.meta


def test_get_by_id_missing(session):
    assert repo.get_by_id(session, 9999) is None


def test_name_inference_from_meta(session, project):
    spectrum = Spectrum(
        wavelengths=np.array([400.0, 500.0]),
        values=np.array([1.0, 2.0]),
        meta={"name": "Meta Name"},
    )
    sid = repo.save(session, spectrum, project.id)
    session.commit()

    orm = session.get(Project, project.id)
    spectrum_orm = next(s for s in orm.spectra if s.id == sid)
    assert spectrum_orm.name == "Meta Name"


def test_name_fallback_when_no_meta(session, project):
    spectrum = Spectrum(
        wavelengths=np.array([400.0, 500.0]),
        values=np.array([1.0, 2.0]),
        meta={},
    )
    sid = repo.save(session, spectrum, project.id, name="Explicit Name")
    session.commit()

    orm = session.get(Project, project.id)
    spectrum_orm = next(s for s in orm.spectra if s.id == sid)
    assert spectrum_orm.name == "Explicit Name"


def test_list_by_project(session, project):
    s1 = Spectrum(
        wavelengths=np.array([400.0, 500.0]),
        values=np.array([1.0, 2.0]),
        meta={"name": "First"},
    )
    s2 = Spectrum(
        wavelengths=np.array([600.0, 700.0]),
        values=np.array([3.0, 4.0]),
        meta={"name": "Second"},
    )
    repo.save(session, s1, project.id)
    repo.save(session, s2, project.id)
    session.commit()

    loaded = repo.list_by_project(session, project.id)
    assert len(loaded) == 2
    assert loaded[0].meta["name"] == "First"
    assert loaded[1].meta["name"] == "Second"


def test_list_by_project_empty(session, project):
    assert repo.list_by_project(session, project.id) == []


def test_delete_removes_spectrum_and_points(session, project, sample_spectrum):
    sid = repo.save(session, sample_spectrum, project.id)
    session.commit()

    assert repo.delete(session, sid) is True
    session.commit()

    assert repo.get_by_id(session, sid) is None


def test_delete_missing_returns_false(session):
    assert repo.delete(session, 9999) is False


def test_fwhm_and_peak_computed_at_save(session, project):
    """FWHM and peak_wavelength should be pre-computed and stored."""
    wl = np.arange(400.0, 701.0, 1.0)
    vals = np.exp(-0.5 * ((wl - 550.0) / 20.0) ** 2)
    spectrum = Spectrum(wavelengths=wl, values=vals, meta={"name": "LED"})
    sid = repo.save(session, spectrum, project.id)
    session.commit()

    from colorlab_pro.database.models import Spectrum as SpectrumORM

    orm = session.get(SpectrumORM, sid)
    assert orm is not None
    assert orm.fwhm is not None
    assert orm.fwhm > 0
    assert orm.peak_wavelength is not None
    assert 540.0 < orm.peak_wavelength < 560.0


def test_fwhm_none_for_flat_spectrum(session, project):
    """Flat spectrum should have fwhm=None, peak_wavelength at first point."""
    wl = np.array([400.0, 500.0, 600.0])
    vals = np.array([1.0, 1.0, 1.0])
    spectrum = Spectrum(wavelengths=wl, values=vals, meta={"name": "Flat"})
    sid = repo.save(session, spectrum, project.id)
    session.commit()

    from colorlab_pro.database.models import Spectrum as SpectrumORM

    orm = session.get(SpectrumORM, sid)
    assert orm is not None
    assert orm.fwhm is None


def test_update_spectrum_fields_returns_false_when_missing(session):
    assert repo.update_spectrum_fields(session, 9999, channel="R") is False


def test_update_spectrum_fields_syncs_meta_json(session, project, sample_spectrum):
    """Updating channel/category/name should also update meta_json."""
    sid = repo.save(session, sample_spectrum, project.id)
    session.commit()

    result = repo.update_spectrum_fields(session, sid, channel="G", category="CF", name="Updated")
    assert result is True
    session.commit()

    from colorlab_pro.database.models import Spectrum as SpectrumORM

    orm = session.get(SpectrumORM, sid)
    assert orm.channel == "G"
    assert orm.category == "CF"
    assert orm.name == "Updated"
    import json

    meta = json.loads(orm.meta_json)
    assert meta["channel"] == "G"
    assert meta["category"] == "CF"
    assert meta["name"] == "Updated"


def test_update_spectrum_fields_corrupt_meta_json(session, project, sample_spectrum):
    """Corrupt meta_json should not crash, just start fresh."""
    sid = repo.save(session, sample_spectrum, project.id)
    session.commit()

    from colorlab_pro.database.models import Spectrum as SpectrumORM

    orm = session.get(SpectrumORM, sid)
    orm.meta_json = "not valid json{{{"
    session.commit()

    result = repo.update_spectrum_fields(session, sid, channel="B")
    assert result is True
    session.commit()

    orm2 = session.get(SpectrumORM, sid)
    import json

    meta = json.loads(orm2.meta_json)
    assert meta["channel"] == "B"


def test_find_duplicate_uses_sql_prefilter(session, project):
    """find_duplicate should use structural metadata to filter candidates."""
    wl = np.array([400.0, 500.0, 600.0])
    vals1 = np.array([0.1, 0.5, 0.9])
    vals2 = np.array([0.2, 0.6, 0.8])

    s1 = Spectrum(wavelengths=wl, values=vals1, meta={"name": "A"})
    s2 = Spectrum(wavelengths=wl, values=vals2, meta={"name": "B"})
    repo.save(session, s1, project.id)
    repo.save(session, s2, project.id)
    session.commit()

    # Exact duplicate of s1
    dup_id = repo.find_duplicate(session, project.id, wl, vals1)
    assert dup_id is not None

    # Different values — no duplicate
    no_dup = repo.find_duplicate(session, project.id, wl, np.array([0.3, 0.7, 0.5]))
    assert no_dup is None
