"""Tests for MixPage and MixViewModel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.pages.mix_page import MixPage


def _make_spec(peak_wl: float) -> Spectrum:
    wls = np.arange(380.0, 781.0, 1.0)
    values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
    return Spectrum(wavelengths=wls, values=values)


@pytest.fixture
def mix_page(tmp_path: Path, qtbot):
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    ctrl = ColorController(main)
    page = MixPage(ctrl)
    qtbot.addWidget(page)
    yield page
    main.shutdown()


class TestMixViewModel:
    def test_add_spectrum(self, mix_page: MixPage) -> None:
        vm = mix_page._view_model
        vm.add_spectrum(_make_spec(620.0))
        assert len(vm.selected_spectra) == 1

    def test_remove_spectrum(self, mix_page: MixPage) -> None:
        vm = mix_page._view_model
        vm.add_spectrum(_make_spec(620.0))
        vm.add_spectrum(_make_spec(520.0))
        vm.remove_spectrum(0)
        assert len(vm.selected_spectra) == 1

    def test_clear_spectra(self, mix_page: MixPage) -> None:
        vm = mix_page._view_model
        vm.add_spectrum(_make_spec(620.0))
        vm.clear_spectra()
        assert len(vm.selected_spectra) == 0
        assert vm.mix_result is None

    def test_mix_two_spectra(self, mix_page: MixPage, qtbot) -> None:
        vm = mix_page._view_model
        vm.add_spectrum(_make_spec(620.0))
        vm.add_spectrum(_make_spec(520.0))
        with qtbot.waitSignal(vm.mix_result_changed, timeout=1000):
            result = vm.mix()
        assert result is not None
        assert result.xyz.Y > 0


class TestMixPage:
    def test_page_creation(self, mix_page: MixPage) -> None:
        assert mix_page._list.count() == 0
        assert mix_page._clear_btn.isEnabled()

    def test_add_one_spectrum(self, mix_page: MixPage) -> None:
        """Adding one spectrum shows hint to add more."""
        mix_page.add_spectrum(_make_spec(620.0))
        assert mix_page._list.count() == 1
        assert "one more" in mix_page._result_label.text().lower()

    def test_add_two_spectra_auto_mix(self, mix_page: MixPage, qtbot) -> None:
        """Adding two spectra auto-triggers mix (synchronous signal chain)."""
        # Start waiting BEFORE adding the second spectrum, since the signal
        # fires synchronously within add_spectrum -> selection_changed -> mix.
        with qtbot.waitSignal(mix_page._view_model.mix_result_changed, timeout=2000):
            mix_page.add_spectrum(_make_spec(620.0))
            mix_page.add_spectrum(_make_spec(520.0))
        assert mix_page._list.count() == 2
        assert "XYZ" in mix_page._result_label.text()

    def test_clear_resets(self, mix_page: MixPage) -> None:
        """Clear button resets the list and result."""
        mix_page.add_spectrum(_make_spec(620.0))
        mix_page._clear_btn.click()
        assert mix_page._list.count() == 0
