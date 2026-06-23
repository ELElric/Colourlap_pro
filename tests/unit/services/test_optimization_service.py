"""Unit tests for OptimizationService."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from colorlab_pro.database.models import Base
from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.repositories import project_repository
from colorlab_pro.services.optimization_service import OptimizationService


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


@pytest.fixture
def service(session_factory):
    return OptimizationService(session_factory)


@pytest.fixture
def project_id(session_factory):
    with session_factory() as session:
        project = project_repository.create(session, "Optimization Project")
        session.commit()
        return int(project.id)


@pytest.fixture
def rgb_primaries() -> list[Spectrum]:
    wavelengths = np.arange(380.0, 781.0, 10.0)
    red = Spectrum(
        wavelengths=wavelengths,
        values=np.where((wavelengths >= 580.0) & (wavelengths <= 700.0), 1.0, 0.05),
    )
    green = Spectrum(
        wavelengths=wavelengths,
        values=np.where((wavelengths >= 500.0) & (wavelengths <= 580.0), 1.0, 0.05),
    )
    blue = Spectrum(
        wavelengths=wavelengths,
        values=np.where((wavelengths >= 400.0) & (wavelengths <= 500.0), 1.0, 0.05),
    )
    return [red, green, blue]


@pytest.fixture
def source_spectrum() -> Spectrum:
    wavelengths = np.arange(380.0, 781.0, 10.0)
    return Spectrum(wavelengths=wavelengths, values=np.ones_like(wavelengths))


@pytest.fixture
def absorbers() -> list[Spectrum]:
    wavelengths = np.arange(380.0, 781.0, 10.0)
    r = Spectrum(wavelengths=wavelengths, values=np.where(wavelengths >= 580.0, 1.0, 0.01))
    g = Spectrum(
        wavelengths=wavelengths,
        values=np.where((wavelengths >= 500.0) & (wavelengths < 580.0), 1.0, 0.01),
    )
    b = Spectrum(wavelengths=wavelengths, values=np.where(wavelengths < 500.0, 1.0, 0.01))
    return [r, g, b]


def test_optimize_white_point(service, rgb_primaries):
    target = XY(x=0.3127, y=0.3290)
    result = service.optimize_white_point(rgb_primaries, target)

    assert "weights" in result
    assert "achieved_xy" in result
    assert "delta_xy" in result
    assert "nearest_white_point" in result
    assert len(result["weights"]) == len(rgb_primaries)
    assert result["delta_xy"] < 0.1


def test_optimize_thickness(service, source_spectrum, absorbers):
    target = XY(x=0.3127, y=0.3290)
    result = service.optimize_thickness(target, source_spectrum, absorbers)

    assert result.converged
    assert len(result.thicknesses_um) == len(absorbers)
    assert all(0.1 <= d <= 10.0 for d in result.thicknesses_um)
    assert result.delta_xy < 0.5


def test_save_optimization(service, project_id, source_spectrum, absorbers):
    target = XY(x=0.3127, y=0.3290)
    result = service.optimize_thickness(target, source_spectrum, absorbers)
    opt_id = service.save_optimization(project_id, "D65 thickness", target, result)

    assert isinstance(opt_id, int)
    assert opt_id > 0
