"""Unit tests for SpectrumService."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import Base
from colorlab_pro.database.models import Spectrum as SpectrumORM
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.repositories import project_repository
from colorlab_pro.services.spectrum_service import SpectrumService


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


@pytest.fixture
def service(session_factory):
    return SpectrumService(session_factory)


@pytest.fixture
def project_id(session_factory):
    with session_factory() as session:
        project = project_repository.create(session, "Service Test Project")
        session.commit()
        return int(project.id)


@pytest.fixture
def sample_spectrum() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([600.0, 610.0, 620.0, 630.0, 640.0]),
        values=np.array([0.1, 0.4, 1.0, 0.6, 0.2]),
        unit="mW/nm",
        meta={"name": "Red LED"},
    )


def test_import_spectrum(service, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum, name="Red")
    assert isinstance(sid, int)

    loaded = service.get_spectrum(sid)
    assert loaded is not None
    # Import preserves the original spectrum data (no forced alignment).
    # Alignment to 380-780 nm is applied on-demand during analysis.
    assert loaded.wavelengths[0] == pytest.approx(600.0)
    assert loaded.wavelengths[-1] == pytest.approx(640.0)
    np.testing.assert_allclose(loaded.values, sample_spectrum.values, atol=1e-10)


def test_import_spectrum_project_not_found(service, sample_spectrum):
    with pytest.raises(ValueError, match="Project 9999 does not exist"):
        service.import_spectrum(9999, sample_spectrum)


def test_import_detects_channel(service, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum)
    assert isinstance(sid, int)


def test_get_spectrum_missing(service):
    assert service.get_spectrum(9999) is None


def test_list_spectra(service, project_id):
    s1 = Spectrum(
        wavelengths=np.array([400.0, 500.0]),
        values=np.array([1.0, 0.0]),
        meta={"name": "First"},
    )
    s2 = Spectrum(
        wavelengths=np.array([600.0, 700.0]),
        values=np.array([0.0, 1.0]),
        meta={"name": "Second"},
    )
    service.import_spectrum(project_id, s1)
    service.import_spectrum(project_id, s2)

    spectra = service.list_spectra(project_id)
    assert len(spectra) == 2
    assert spectra[0].meta["name"] == "First"
    assert spectra[1].meta["name"] == "Second"


def test_delete_spectrum(service, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum)
    assert service.delete_spectrum(sid) is True
    assert service.get_spectrum(sid) is None


def test_delete_spectrum_missing(service):
    assert service.delete_spectrum(9999) is False


def test_detect_channel_delegate(service, sample_spectrum):
    channel = service.detect_channel(sample_spectrum)
    assert isinstance(channel, str)


def test_analyze(service, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum)
    result = service.analyze(sid)

    assert result is not None
    assert "xyz" in result
    assert "xy" in result
    assert "uprime_vprime" in result
    assert "cct" in result
    assert "dominant_wavelength" in result


def test_analyze_missing(service):
    assert service.analyze(9999) is None


def test_import_with_explicit_channel_derives_category(
    service, session_factory, project_id, sample_spectrum
):
    sid = service.import_spectrum(project_id, sample_spectrum, channel="R", category=None)
    with session_factory() as session:
        orm = session.get(SpectrumORM, sid)
        assert orm is not None
        assert orm.channel == "R"
        assert orm.category == "LED"


def test_import_with_explicit_category(service, session_factory, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum, channel="R", category="Custom")
    with session_factory() as session:
        orm = session.get(SpectrumORM, sid)
        assert orm.category == "Custom"


def test_update_channel(service, session_factory, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum)
    assert service.update_channel(sid, "G") is True
    with session_factory() as session:
        orm = session.get(SpectrumORM, sid)
        assert orm.channel == "G"


def test_update_channel_missing(service):
    assert service.update_channel(9999, "G") is False


def test_preprocess_normalize(service, session_factory, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum, name="Source")
    new_id = service.preprocess(sid, normalize_mode="peak", suffix="_norm")
    assert isinstance(new_id, int)
    assert new_id != sid

    loaded = service.get_spectrum(new_id)
    assert loaded is not None
    assert loaded.meta["normalize"] == "peak"
    with session_factory() as session:
        orm = session.get(SpectrumORM, new_id)
        assert orm.name == "Source_norm"


def test_preprocess_interpolate(service, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum)
    new_id = service.preprocess(sid, interpolate_step=1, suffix="_1nm")
    assert isinstance(new_id, int)
    loaded = service.get_spectrum(new_id)
    assert loaded is not None
    # Original spectrum is 600-640 nm at 1 nm step = 41 points.
    # Interpolation to 1 nm step preserves the point count.
    assert loaded.wavelengths.size == 41


def test_preprocess_fill_gaps(service, project_id, sample_spectrum):
    sid = service.import_spectrum(project_id, sample_spectrum, name="Source")
    new_id = service.preprocess(sid, fill_gaps=True, suffix="_filled")
    assert isinstance(new_id, int)
    loaded = service.get_spectrum(new_id)
    assert loaded is not None


def test_preprocess_missing(service):
    assert service.preprocess(9999, normalize_mode="peak") is None
