"""Tests for SpectrumController."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController, SpectrumSummary
from colorlab_pro.dto.spectrum import Spectrum


@pytest.fixture
def spectrum_ctrl(tmp_path: Path):
    """Provide a SpectrumController with a project and in-memory DB."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")

    proj_ctrl = ProjectController(main)
    pid = proj_ctrl.create_project("Test Project")
    main.set_current_project(pid)

    ctrl = SpectrumController(main)
    yield ctrl
    main.shutdown()


class TestImport:
    def test_import_spectrum(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(
            wavelengths=np.array([400.0, 500.0, 600.0]),
            values=np.array([0.1, 0.5, 0.9]),
        )
        imported_ids: list[int] = []
        spectrum_ctrl.spectrum_imported.connect(lambda sid: imported_ids.append(sid))
        sid = spectrum_ctrl.import_spectrum(spec, name="Test")
        assert sid is not None
        assert isinstance(sid, int)
        assert sid in imported_ids  # signal emitted

    def test_import_spectrum_no_project(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.set_current_project(None)
        spec = Spectrum(wavelengths=np.array([400.0]), values=np.array([0.1]))
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.import_spectrum(spec)
        assert result is None
        assert errors  # error signal emitted

    def test_import_csv_file(self, spectrum_ctrl: SpectrumController, tmp_path: Path) -> None:
        csv_path = tmp_path / "spectrum.csv"
        csv_path.write_text("400,0.1\n500,0.5\n600,0.9\n")
        sid = spectrum_ctrl.import_csv_file(csv_path, name="From CSV")
        assert sid is not None


class TestList:
    def test_list_empty_when_no_project(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.set_current_project(None)
        assert spectrum_ctrl.list_spectra() == []

    def test_list_after_import(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(
            wavelengths=np.array([400.0, 500.0]),
            values=np.array([0.1, 0.5]),
        )
        spectrum_ctrl.import_spectrum(spec, name="Listed")
        summaries = spectrum_ctrl.list_spectra()
        assert len(summaries) == 1
        assert summaries[0].name == "Listed"
        assert isinstance(summaries[0], SpectrumSummary)


class TestGet:
    def test_get_existing(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(
            wavelengths=np.array([380.0, 400.0, 780.0]),
            values=np.array([0.0, 0.1, 0.0]),
        )
        sid = spectrum_ctrl.import_spectrum(spec, name="Get Me")
        loaded = spectrum_ctrl.get_spectrum(sid)
        assert loaded is not None
        idx_400 = int(np.argmin(np.abs(loaded.wavelengths - 400.0)))
        assert np.isclose(loaded.values[idx_400], 0.1, atol=1e-6)

    def test_get_missing(self, spectrum_ctrl: SpectrumController) -> None:
        assert spectrum_ctrl.get_spectrum(9999) is None


class TestDelete:
    def test_delete_existing(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(
            wavelengths=np.array([380.0, 400.0, 780.0]),
            values=np.array([0.0, 0.1, 0.0]),
        )
        sid = spectrum_ctrl.import_spectrum(spec)
        deleted_ids: list[int] = []
        spectrum_ctrl.spectrum_deleted.connect(lambda sid: deleted_ids.append(sid))
        result = spectrum_ctrl.delete_spectrum(sid)
        assert result is True
        assert sid in deleted_ids  # signal emitted
        assert spectrum_ctrl.get_spectrum(sid) is None

    def test_delete_missing(self, spectrum_ctrl: SpectrumController) -> None:
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.delete_spectrum(9999)
        assert result is False
        assert errors


class TestAnalyze:
    def test_analyze_existing(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(
            wavelengths=np.linspace(380, 780, 401),
            values=np.ones(401),
        )
        sid = spectrum_ctrl.import_spectrum(spec)
        results: list[dict] = []
        spectrum_ctrl.analysis_ready.connect(lambda r: results.append(r))
        result = spectrum_ctrl.analyze_spectrum(sid)
        assert result is not None
        assert "xyz" in result
        assert "xy" in result
        assert results  # signal emitted

    def test_analyze_missing(self, spectrum_ctrl: SpectrumController) -> None:
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.analyze_spectrum(9999)
        assert result is None
        assert errors

    def test_analyze_exception(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(
            wavelengths=np.linspace(380, 780, 401),
            values=np.ones(401),
        )
        sid = spectrum_ctrl.import_spectrum(spec)
        spectrum_ctrl._main.spectrum_service.analyze = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("analyze failed"))
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.analyze_spectrum(sid)
        assert result is None
        assert errors


class TestServiceAvailability:
    def test_spectrum_service_unavailable(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.spectrum_service = None
        with pytest.raises(RuntimeError, match="SpectrumService not available"):
            spectrum_ctrl._service()


class TestImportFileErrors:
    def test_import_csv_file_load_error(
        self, spectrum_ctrl: SpectrumController, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("not valid")
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch(
            "colorlab_pro.controllers.spectrum_controller.import_csv",
            side_effect=RuntimeError("csv parse error"),
        ):
            result = spectrum_ctrl.import_csv_file(csv_path)
        assert result is None
        assert errors

    def test_import_xlsx_file_load_error(
        self, spectrum_ctrl: SpectrumController, tmp_path: Path
    ) -> None:
        xlsx_path = tmp_path / "bad.xlsx"
        xlsx_path.write_text("not valid")
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch(
            "colorlab_pro.controllers.spectrum_controller.import_xlsx",
            side_effect=RuntimeError("xlsx parse error"),
        ):
            result = spectrum_ctrl.import_xlsx_file(xlsx_path)
        assert result is None
        assert errors

    def test_import_xlsx_file_success(
        self, spectrum_ctrl: SpectrumController, tmp_path: Path
    ) -> None:
        xlsx_path = tmp_path / "spectrum.xlsx"
        xlsx_path.write_text("ignored")
        spec = Spectrum(wavelengths=np.array([400.0, 500.0]), values=np.array([0.1, 0.5]))
        imported_ids: list[int] = []
        spectrum_ctrl.spectrum_imported.connect(lambda sid: imported_ids.append(sid))
        with patch("colorlab_pro.controllers.spectrum_controller.import_xlsx", return_value=spec):
            sid = spectrum_ctrl.import_xlsx_file(xlsx_path, name="From XLSX")
        assert sid is not None
        assert isinstance(sid, int)
        assert sid in imported_ids


class TestRenameSpectrum:
    def test_rename_spectrum_success(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(wavelengths=np.array([400.0, 500.0]), values=np.array([0.1, 0.5]))
        sid = spectrum_ctrl.import_spectrum(spec, name="Old Name")
        updated: list = []
        spectrum_ctrl.spectra_updated.connect(lambda: updated.append(True))
        result = spectrum_ctrl.rename_spectrum(sid, "New Name")
        assert result is True
        assert updated  # signal emitted
        summaries = spectrum_ctrl.list_spectra()
        assert any(s.name == "New Name" for s in summaries)

    def test_rename_spectrum_not_found(self, spectrum_ctrl: SpectrumController) -> None:
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.rename_spectrum(9999, "X")
        assert result is False
        assert errors

    def test_rename_spectrum_exception(self, spectrum_ctrl: SpectrumController) -> None:
        class _RaisingContext:
            def __enter__(self):
                raise RuntimeError("db fail")

            def __exit__(self, *args):
                return False

        spectrum_ctrl._main._session_factory = lambda: _RaisingContext()
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.rename_spectrum(1, "X")
        assert result is False
        assert errors


class TestDuplicateSpectrum:
    def test_duplicate_spectrum_success(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(wavelengths=np.array([400.0, 500.0]), values=np.array([0.1, 0.5]))
        sid = spectrum_ctrl.import_spectrum(spec, name="Original", channel="R", category="red")
        imported_ids: list[int] = []
        spectrum_ctrl.spectrum_imported.connect(lambda sid: imported_ids.append(sid))
        new_id = spectrum_ctrl.duplicate_spectrum(sid)
        assert new_id is not None
        assert isinstance(new_id, int)
        assert new_id != sid
        assert new_id in imported_ids  # signal emitted
        summaries = spectrum_ctrl.list_spectra()
        # get_spectrum does not populate meta['name'], so the copy uses the default name
        assert any(s.name == "Spectrum (copy)" for s in summaries)

    def test_duplicate_spectrum_missing(self, spectrum_ctrl: SpectrumController) -> None:
        assert spectrum_ctrl.duplicate_spectrum(9999) is None


class TestListSpectraExceptions:
    def test_list_spectra_exception(self, spectrum_ctrl: SpectrumController) -> None:
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        with patch("sqlalchemy.select", side_effect=RuntimeError("select failed")):
            result = spectrum_ctrl.list_spectra()
        assert result == []
        assert errors


class TestGetSpectrum:
    def test_get_spectrum_exception(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.spectrum_service.get_spectrum = lambda sid: (_ for _ in ()).throw(
            RuntimeError("get failed")
        )
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.get_spectrum(1)
        assert result is None
        assert errors


class TestDeleteSpectrum:
    def test_delete_spectrum_exception(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.spectrum_service.delete_spectrum = lambda sid: (_ for _ in ()).throw(
            RuntimeError("delete failed")
        )
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.delete_spectrum(1)
        assert result is False
        assert errors


class TestDetectChannel:
    def test_detect_channel(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        channel = spectrum_ctrl.detect_channel(spec)
        assert isinstance(channel, str)


class TestUpdateChannel:
    def test_update_channel_success(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(wavelengths=np.array([400.0, 500.0]), values=np.array([0.1, 0.5]))
        sid = spectrum_ctrl.import_spectrum(spec, name="Chan")
        updated: list = []
        spectrum_ctrl.spectra_updated.connect(lambda: updated.append(True))
        result = spectrum_ctrl.update_channel(sid, "G")
        assert result is True
        assert updated  # signal emitted

    def test_update_channel_exception(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.spectrum_service.update_channel = lambda sid, ch: (_ for _ in ()).throw(
            RuntimeError("update failed")
        )
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.update_channel(1, "G")
        assert result is False
        assert errors


class TestPreprocessSpectrum:
    def test_preprocess_spectrum_success(self, spectrum_ctrl: SpectrumController) -> None:
        spec = Spectrum(wavelengths=np.linspace(380, 780, 401), values=np.ones(401))
        sid = spectrum_ctrl.import_spectrum(spec, name="Pre")
        imported_ids: list[int] = []
        updated_flags: list = []
        spectrum_ctrl.spectra_updated.connect(lambda: updated_flags.append(True))
        spectrum_ctrl.spectrum_imported.connect(lambda sid: imported_ids.append(sid))
        new_id = spectrum_ctrl.preprocess_spectrum(sid, normalize_mode="peak")
        assert new_id is not None
        assert isinstance(new_id, int)
        assert new_id in imported_ids  # spectrum_imported emitted
        assert updated_flags  # spectra_updated emitted

    def test_preprocess_spectrum_exception(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.spectrum_service.preprocess = lambda *args, **kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("preprocess failed"))
        errors: list[str] = []
        spectrum_ctrl.error_occurred.connect(lambda msg: errors.append(msg))
        result = spectrum_ctrl.preprocess_spectrum(1, normalize_mode="peak")
        assert result is None
        assert errors

    def test_preprocess_spectrum_returns_none(self, spectrum_ctrl: SpectrumController) -> None:
        spectrum_ctrl._main.spectrum_service.preprocess = lambda *args, **kwargs: None
        result = spectrum_ctrl.preprocess_spectrum(1, normalize_mode="peak")
        assert result is None
