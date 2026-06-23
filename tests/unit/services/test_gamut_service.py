"""Unit tests for GamutService."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.color import XY, Gamut
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.services.gamut_service import GamutService


@pytest.fixture
def service():
    return GamutService()


@pytest.fixture
def red_primary() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([600.0, 610.0, 620.0, 630.0, 640.0]),
        values=np.array([0.1, 0.4, 1.0, 0.6, 0.2]),
    )


@pytest.fixture
def green_primary() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([500.0, 510.0, 520.0, 530.0, 540.0]),
        values=np.array([0.1, 0.5, 1.0, 0.5, 0.1]),
    )


@pytest.fixture
def blue_primary() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([440.0, 450.0, 460.0, 470.0, 480.0]),
        values=np.array([0.1, 0.5, 1.0, 0.5, 0.1]),
    )


def test_build_from_primaries(service, red_primary, green_primary, blue_primary):
    gamut = service.build_from_primaries(red_primary, green_primary, blue_primary)
    assert isinstance(gamut, Gamut)
    assert gamut.name == "custom"


def test_standard_gamut(service):
    gamut = service.standard_gamut("sRGB")
    assert isinstance(gamut, Gamut)
    assert gamut.name == "sRGB"


def test_list_standard_gamuts(service):
    names = service.list_standard_gamuts()
    assert "sRGB" in names
    assert "DCI-P3" in names


def test_coverage(service):
    device = Gamut(
        name="device",
        red=(0.64, 0.33),
        green=(0.30, 0.60),
        blue=(0.15, 0.06),
        white=(0.3127, 0.3290),
    )
    cov = service.coverage("sRGB", device)
    assert 0.0 <= cov <= 100.0 + 1e-9


def test_match(service):
    device = service.standard_gamut("sRGB")
    score = service.match("sRGB", device)
    assert score == pytest.approx(100.0, abs=0.01)


def test_area(service):
    gamut = service.standard_gamut("sRGB")
    assert service.area(gamut) > 0.0


def test_contains(service):
    gamut = service.standard_gamut("sRGB")
    assert service.contains(gamut, XY(x=0.3127, y=0.3290)) is True


def test_coverage_1976(service):
    device = service.standard_gamut("sRGB")
    cov = service.coverage_1976("DCI-P3", device)
    assert cov > 0.0


def test_match_1976(service):
    device = service.standard_gamut("sRGB")
    m = service.match_1976("sRGB", device)
    assert m == pytest.approx(100.0, abs=0.01)


def test_match_spectrum(service):
    m = service.match_spectrum(XY(0.3, 0.4), XY(0.3, 0.4))
    assert m == pytest.approx(100.0)
