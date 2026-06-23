"""Tests for SpectrumPage and SpectrumViewModel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.pages.spectrum_page import SpectrumPage


@pytest.fixture
def spectrum_page(tmp_path: Path, qtbot):
    """Provide a SpectrumPage with a project and in-memory DB."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    proj_ctrl = ProjectController(main)
    pid = proj_ctrl.create_project("Test Project")
    main.set_current_project(pid)

    spec_ctrl = SpectrumController(main)
    page = SpectrumPage(spec_ctrl)
    qtbot.addWidget(page)
    yield page
    main.shutdown()


class TestSpectrumViewModel:
    def test_refresh_empty(self, spectrum_page: SpectrumPage) -> None:
        vm = spectrum_page._view_model
        vm.refresh()
        assert vm.spectra == []

    def test_import_and_refresh(self, spectrum_page: SpectrumPage) -> None:
        vm = spectrum_page._view_model
        spec = Spectrum(wavelengths=np.arange(380.0, 781.0, 1.0), values=np.ones(401))
        vm.import_spectrum(spec, name="Test")
        vm.refresh()
        assert len(vm.spectra) == 1
        assert vm.spectra[0].name == "Test"

    def test_select_spectrum(self, spectrum_page: SpectrumPage, qtbot) -> None:
        vm = spectrum_page._view_model
        spec = Spectrum(wavelengths=np.arange(380.0, 781.0, 1.0), values=np.ones(401))
        sid = vm.import_spectrum(spec, name="Selectable")
        with qtbot.waitSignal(vm.selection_changed, timeout=1000):
            vm.select_spectrum(sid)
        assert vm.selected_spectrum is not None

    def test_delete_spectrum(self, spectrum_page: SpectrumPage) -> None:
        vm = spectrum_page._view_model
        spec = Spectrum(wavelengths=np.arange(380.0, 781.0, 1.0), values=np.ones(401))
        sid = vm.import_spectrum(spec, name="Deletable")
        vm.delete_spectrum(sid)
        vm.refresh()
        assert len(vm.spectra) == 0


class TestSpectrumPage:
    def test_page_creation(self, spectrum_page: SpectrumPage) -> None:
        assert spectrum_page._table.rowCount() == 0
        # Delete button is disabled when no spectrum is selected
        assert not spectrum_page._delete_btn.isEnabled()

    def test_refresh_populates_table(self, spectrum_page: SpectrumPage) -> None:
        vm = spectrum_page._view_model
        spec = Spectrum(wavelengths=np.arange(380.0, 781.0, 1.0), values=np.ones(401))
        vm.import_spectrum(spec, name="S1")
        spectrum_page.refresh()
        assert spectrum_page._table.rowCount() == 1

    def test_select_triggers_auto_analysis(self, spectrum_page: SpectrumPage, qtbot) -> None:
        """Selecting a spectrum auto-triggers analysis (no button needed)."""
        vm = spectrum_page._view_model
        spec = Spectrum(wavelengths=np.arange(380.0, 781.0, 1.0), values=np.ones(401))
        sid = vm.import_spectrum(spec, name="AutoAnalyze")
        vm.refresh()
        # Select the spectrum — this should auto-analyze
        with qtbot.waitSignal(vm.analysis_updated, timeout=2000):
            vm.select_spectrum(sid)
        # Info panel should contain xy values (not dash)
        assert spectrum_page._info_cards["xy"].text() != "-"
