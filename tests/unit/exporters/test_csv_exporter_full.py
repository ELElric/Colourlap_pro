"""Additional unit tests for CSV exporter/importer."""

from __future__ import annotations

import csv

import numpy as np
import pytest

from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.exporters.csv_exporter import export_spectrum, import_spectrum


@pytest.fixture
def sample_spectrum() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([400.0, 500.0, 600.0]),
        values=np.array([0.1, 0.5, 0.9]),
        unit="mW/nm",
    )


def test_export_spectrum_creates_file(tmp_path, sample_spectrum):
    path = tmp_path / "nested" / "spectrum.csv"
    export_spectrum(sample_spectrum, path)
    assert path.exists()
    assert path.parent.exists()


def test_import_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV file is empty"):
        import_spectrum(path)


def test_import_invalid_numeric_row(tmp_path):
    path = tmp_path / "invalid.csv"
    path.write_text("wavelength_nm,value\n400,0.1\n500,bad\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid numeric row"):
        import_spectrum(path)


def test_import_missing_unit_column(tmp_path):
    path = tmp_path / "no_unit.csv"
    path.write_text("wavelength_nm,value\n400,0.1\n500,0.5\n600,0.9\n", encoding="utf-8")
    spectrum = import_spectrum(path)
    assert spectrum.unit == "a.u."


def test_import_with_unit_column(tmp_path):
    path = tmp_path / "with_unit.csv"
    path.write_text(
        "wavelength_nm,value,unit\n400,0.1,mW/nm\n500,0.5,mW/nm\n600,0.9,mW/nm\n", encoding="utf-8"
    )
    spectrum = import_spectrum(path)
    assert spectrum.unit == "mW/nm"


def test_import_with_unit_column_blank_fallback(tmp_path):
    path = tmp_path / "blank_unit.csv"
    path.write_text("wavelength_nm,value,unit\n400,0.1,\n500,0.5,\n600,0.9,\n", encoding="utf-8")
    spectrum = import_spectrum(path, unit="fallback")
    assert spectrum.unit == "fallback"


def test_import_too_few_points(tmp_path):
    path = tmp_path / "too_few.csv"
    path.write_text("wavelength_nm,value\n400,0.1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="At least two data points are required"):
        import_spectrum(path)


def test_import_ignores_blank_rows(tmp_path):
    path = tmp_path / "blanks.csv"
    path.write_text("wavelength_nm,value\n400,0.1\n\n500,0.5\n600,0.9\n", encoding="utf-8")
    spectrum = import_spectrum(path)
    np.testing.assert_array_equal(spectrum.wavelengths, np.array([400.0, 500.0, 600.0]))


def test_export_import_preserves_unit_default(tmp_path):
    spectrum = Spectrum(
        wavelengths=np.array([400.0, 500.0]),
        values=np.array([0.1, 0.5]),
    )
    path = tmp_path / "default_unit.csv"
    export_spectrum(spectrum, path)
    loaded = import_spectrum(path)
    assert loaded.unit == "a.u."


def test_exported_csv_format(tmp_path, sample_spectrum):
    path = tmp_path / "format.csv"
    export_spectrum(sample_spectrum, path)
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    assert rows[0] == ["wavelength_nm", "value", "unit"]
    assert rows[1] == ["400.0", "0.1", "mW/nm"]
