"""Unit tests for ColorService."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import Base
from colorlab_pro.dto.color import XY, XYZ
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.repositories import project_repository, spectrum_repository
from colorlab_pro.services.color_service import ColorService


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


@pytest.fixture
def service(session_factory):
    return ColorService(session_factory)


@pytest.fixture
def red_spectrum() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([600.0, 610.0, 620.0, 630.0, 640.0]),
        values=np.array([0.1, 0.4, 1.0, 0.6, 0.2]),
        meta={"name": "Red"},
    )


@pytest.fixture
def green_spectrum() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([500.0, 510.0, 520.0, 530.0, 540.0]),
        values=np.array([0.1, 0.5, 1.0, 0.5, 0.1]),
        meta={"name": "Green"},
    )


def test_mix_spectra(service, red_spectrum, green_spectrum):
    mixed = service.mix_spectra([red_spectrum, green_spectrum])
    assert isinstance(mixed, Spectrum)
    np.testing.assert_array_equal(mixed.wavelengths, red_spectrum.wavelengths)


def test_mixed_xyz(service, red_spectrum, green_spectrum):
    result = service.mixed_xyz([red_spectrum, green_spectrum])
    assert isinstance(result, XYZ)
    assert result.X >= 0


def test_mixed_xy(service):
    xy_list = [XY(x=0.64, y=0.33), XY(x=0.30, y=0.60)]
    result = service.mixed_xy(xy_list)
    assert isinstance(result, XY)


def test_luminance(service, red_spectrum):
    y = service.luminance(red_spectrum)
    assert isinstance(y, float)
    assert y >= 0


def test_delta_uv_to_d65(service, red_spectrum):
    duv = service.delta_uv_to_d65(red_spectrum)
    assert isinstance(duv, float)


def test_mix_spectra_by_id(service, session_factory, red_spectrum, green_spectrum):
    with session_factory() as session:
        project = project_repository.create(session, "Mix Project")
        rid = spectrum_repository.save(session, red_spectrum, project.id)
        gid = spectrum_repository.save(session, green_spectrum, project.id)
        session.commit()

    mixed = service.mix_spectra_by_id([rid, gid])
    assert isinstance(mixed, Spectrum)


def test_mix_spectra_by_id_missing(service):
    with pytest.raises(ValueError, match="Spectrum 9999 not found"):
        service.mix_spectra_by_id([9999])


def test_delta_e(service, red_spectrum, green_spectrum):
    """Test delta_e method returns a valid color difference."""
    result = service.delta_e(red_spectrum, green_spectrum)
    assert isinstance(result, float)
    assert result >= 0


def test_delta_e_same_spectrum(service, red_spectrum):
    """Test delta_e of identical spectra is approximately zero."""
    result = service.delta_e(red_spectrum, red_spectrum)
    assert result == pytest.approx(0.0, abs=1e-9)
