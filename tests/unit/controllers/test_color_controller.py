"""Tests for ColorController."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from colorlab_pro.controllers.color_controller import ColorController, GamutResult, MixResult
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.dto.spectrum import Spectrum


@pytest.fixture
def color_ctrl(tmp_path: Path, qtbot):
    """Provide a ColorController with an in-memory database."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    ctrl = ColorController(main)
    yield ctrl
    main.shutdown()


class TestMixSpectra:
    def _make_spec(self, peak_wl: float) -> Spectrum:
        """Create a 1nm-step spectrum with a Gaussian peak."""
        wls = np.arange(380.0, 781.0, 1.0)
        values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
        return Spectrum(wavelengths=wls, values=values)

    def test_mix_two_spectra(self, color_ctrl: ColorController, qtbot) -> None:
        s1 = self._make_spec(620.0)
        s2 = self._make_spec(520.0)
        with qtbot.waitSignal(color_ctrl.mix_ready, timeout=1000):
            result = color_ctrl.mix_spectra([s1, s2])
        assert result is not None
        assert isinstance(result, MixResult)
        assert len(result.spectrum.wavelengths) == 401

    def test_mix_with_weights(self, color_ctrl: ColorController) -> None:
        s1 = self._make_spec(620.0)
        s2 = self._make_spec(520.0)
        result = color_ctrl.mix_spectra([s1, s2], weights=[1.0, 0.0])
        assert result is not None
        assert np.isclose(result.spectrum.values[200], s1.values[200])


class TestGamut:
    def test_build_gamut_from_primaries(self, color_ctrl: ColorController, qtbot) -> None:
        wls = np.arange(380.0, 781.0, 1.0)
        red = Spectrum(wavelengths=wls, values=np.exp(-0.5 * ((wls - 620.0) / 20.0) ** 2))
        green = Spectrum(wavelengths=wls, values=np.exp(-0.5 * ((wls - 520.0) / 20.0) ** 2))
        blue = Spectrum(wavelengths=wls, values=np.exp(-0.5 * ((wls - 460.0) / 20.0) ** 2))
        with qtbot.waitSignal(color_ctrl.gamut_ready, timeout=1000):
            result = color_ctrl.build_gamut_from_primaries(red, green, blue, name="test")
        assert result is not None
        assert isinstance(result, GamutResult)
        assert result.name == "test"
        assert result.area > 0

    def test_list_standard_gamuts(self, color_ctrl: ColorController) -> None:
        names = color_ctrl.list_standard_gamuts()
        assert "sRGB" in names
        assert "DCI-P3" in names

    def test_compare_to_standard(self, color_ctrl: ColorController, qtbot) -> None:
        with qtbot.waitSignal(color_ctrl.gamut_ready, timeout=1000):
            result = color_ctrl.compare_to_standard("sRGB", "sRGB")
        assert result is not None
        assert result["coverage"] == pytest.approx(100.0, abs=1e-9)
        assert result["match"] == pytest.approx(100.0, abs=1e-9)


class TestAnalysisHelpers:
    def test_luminance(self, color_ctrl: ColorController) -> None:
        spec = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        y = color_ctrl.luminance(spec)
        assert y > 0

    def test_delta_uv_to_d65(self, color_ctrl: ColorController) -> None:
        spec = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        duv = color_ctrl.delta_uv_to_d65(spec)
        assert isinstance(duv, float)

    def test_delta_e(self, color_ctrl: ColorController) -> None:
        spec_a = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        spec_b = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401) * 0.9)
        result = color_ctrl.delta_e(spec_a, spec_b)
        assert isinstance(result, float)

    def test_delta_e_error(self, color_ctrl: ColorController, qtbot) -> None:
        spec = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        color_ctrl._main.color_service.delta_e = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("delta-e error")
        )
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.delta_e(spec, spec)
        assert result is None


class TestServiceAvailability:
    def test_color_service_unavailable(self, color_ctrl: ColorController) -> None:
        color_ctrl._main.color_service = None
        with pytest.raises(RuntimeError, match="ColorService not available"):
            color_ctrl._color_service()

    def test_gamut_service_unavailable(self, color_ctrl: ColorController) -> None:
        color_ctrl._main.gamut_service = None
        with pytest.raises(RuntimeError, match="GamutService not available"):
            color_ctrl._gamut_service()


class TestMixErrors:
    def _make_spec(self, peak_wl: float) -> Spectrum:
        wls = np.arange(380.0, 781.0, 1.0)
        values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
        return Spectrum(wavelengths=wls, values=values)

    def test_mix_spectra_error(self, color_ctrl: ColorController, qtbot) -> None:
        spec = self._make_spec(550.0)
        color_ctrl._main.color_service.mix_spectra = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("mix failed")
        )
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.mix_spectra([spec])
        assert result is None


class TestMixById:
    def _make_spec(self, peak_wl: float) -> Spectrum:
        wls = np.arange(380.0, 781.0, 1.0)
        values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
        return Spectrum(wavelengths=wls, values=values)

    def test_mix_spectra_by_id_success(self, color_ctrl: ColorController, qtbot) -> None:
        from colorlab_pro.controllers.project_controller import ProjectController

        pid = ProjectController(color_ctrl._main).create_project("mix")
        s1 = color_ctrl._main.spectrum_service.import_spectrum(
            pid, self._make_spec(620.0), name="R"
        )
        s2 = color_ctrl._main.spectrum_service.import_spectrum(
            pid, self._make_spec(520.0), name="G"
        )
        with qtbot.waitSignal(color_ctrl.mix_ready, timeout=1000):
            result = color_ctrl.mix_spectra_by_id([s1, s2])
        assert result is not None
        assert isinstance(result, MixResult)

    def test_mix_spectra_by_id_service_error(self, color_ctrl: ColorController, qtbot) -> None:
        color_ctrl._main.color_service.mix_spectra_by_id = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("id mix failed"))
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.mix_spectra_by_id([1, 2])
        assert result is None

    def test_mix_spectra_by_id_load_failure(self, color_ctrl: ColorController, qtbot) -> None:
        color_ctrl._main.color_service.mix_spectra_by_id = lambda *args, **kwargs: None
        color_ctrl._main.spectrum_service.get_spectrum = lambda sid: None
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.mix_spectra_by_id([1])
        assert result is None


class TestGamutErrors:
    def _make_spec(self, peak_wl: float) -> Spectrum:
        wls = np.arange(380.0, 781.0, 1.0)
        values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
        return Spectrum(wavelengths=wls, values=values)

    def test_build_gamut_from_primaries_with_white(
        self, color_ctrl: ColorController, qtbot
    ) -> None:
        red = self._make_spec(620.0)
        green = self._make_spec(520.0)
        blue = self._make_spec(460.0)
        white = self._make_spec(550.0)
        with qtbot.waitSignal(color_ctrl.gamut_ready, timeout=1000):
            result = color_ctrl.build_gamut_from_primaries(
                red, green, blue, white=white, name="with-white"
            )
        assert result is not None
        assert result.name == "with-white"

    def test_build_gamut_from_primaries_error(self, color_ctrl: ColorController, qtbot) -> None:
        color_ctrl._main.gamut_service.build_from_primaries = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("gamut failed"))
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.build_gamut_from_primaries(
                self._make_spec(620.0), self._make_spec(520.0), self._make_spec(460.0)
            )
        assert result is None

    def test_compare_to_standard_error(self, color_ctrl: ColorController, qtbot) -> None:
        color_ctrl._main.gamut_service.standard_gamut = lambda name: (_ for _ in ()).throw(
            RuntimeError("no gamut")
        )
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.compare_to_standard("sRGB", "custom")
        assert result is None


class TestProjectGamutCoverage:
    def _make_spec(self, peak_wl: float) -> Spectrum:
        wls = np.arange(380.0, 781.0, 1.0)
        values = np.exp(-0.5 * ((wls - peak_wl) / 20.0) ** 2)
        return Spectrum(wavelengths=wls, values=values)

    def test_project_gamut_coverage_too_few_spectra(
        self, color_ctrl: ColorController, qtbot
    ) -> None:
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.project_gamut_coverage("sRGB", [self._make_spec(620.0)])
        assert result is None

    def test_project_gamut_coverage_success(self, color_ctrl: ColorController) -> None:
        spectra = [self._make_spec(620.0), self._make_spec(520.0), self._make_spec(460.0)]
        result = color_ctrl.project_gamut_coverage("sRGB", spectra)
        assert result is not None
        assert "coverage" in result
        assert "match" in result
        assert "area" in result

    def test_project_gamut_coverage_error(self, color_ctrl: ColorController, qtbot) -> None:
        color_ctrl._main.gamut_service.build_from_primaries = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("build failed"))
        spectra = [self._make_spec(620.0), self._make_spec(520.0), self._make_spec(460.0)]
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.project_gamut_coverage("sRGB", spectra)
        assert result is None


class TestSpectrumVsGamut:
    def test_spectrum_vs_gamut(self, color_ctrl: ColorController) -> None:
        # The production GamutService does not expose match_spectrum, so patch it in.
        color_ctrl._main.gamut_service.match_spectrum = lambda white, spectrum: 0.9
        spec = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        result = color_ctrl.spectrum_vs_gamut(spec, "sRGB")
        assert result is not None
        assert "inside" in result
        assert "match" in result
        assert "xy" in result

    def test_spectrum_vs_gamut_error(self, color_ctrl: ColorController, qtbot) -> None:
        color_ctrl._main.gamut_service.standard_gamut = lambda name: (_ for _ in ()).throw(
            RuntimeError("missing")
        )
        spec = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        with qtbot.waitSignal(color_ctrl.error_occurred, timeout=1000):
            result = color_ctrl.spectrum_vs_gamut(spec, "sRGB")
        assert result is None
