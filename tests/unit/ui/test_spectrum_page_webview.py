"""Tests for the WebView-based SpectrumPage backend."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.pages.spectrum_page import SpectrumPageBackend


@pytest.fixture
def backend(tmp_path: Path):
    """Provide a SpectrumPageBackend with a project and in-memory DB."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    proj_ctrl = ProjectController(main)
    pid = proj_ctrl.create_project("Test Project")
    main.set_current_project(pid)
    spec_ctrl = SpectrumController(main)
    backend = SpectrumPageBackend(spec_ctrl)
    yield backend
    main.shutdown()


class TestSpectrumPageBackend:
    def test_get_spectra_empty(self, backend: SpectrumPageBackend) -> None:
        raw = backend.get_spectra()
        data = json.loads(raw)
        assert data == []

    def test_get_spectra_with_data(self, backend: SpectrumPageBackend) -> None:
        wavelengths = np.arange(380.0, 781.0, 1.0)
        values = np.exp(-((wavelengths - 630.0) ** 2) / (2 * 20**2))
        backend._controller.import_spectrum(Spectrum(wavelengths=wavelengths, values=values), name="Red")
        raw = backend.get_spectra()
        data = json.loads(raw)
        assert len(data) == 1
        assert data[0]["name"] == "Red"
        assert isinstance(data[0]["data"], list)
        assert len(data[0]["data"]) > 0

    def test_get_spectra_includes_chart_data(self, backend: SpectrumPageBackend) -> None:
        wavelengths = np.arange(380.0, 781.0, 1.0)
        values = np.ones_like(wavelengths)
        backend._controller.import_spectrum(Spectrum(wavelengths=wavelengths, values=values), name="Flat")
        raw = backend.get_spectra()
        data = json.loads(raw)
        point = data[0]["data"][0]
        assert len(point) == 2
        assert point[0] == 380.0
