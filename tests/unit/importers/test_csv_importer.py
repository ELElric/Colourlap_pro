"""Unit tests for CSV spectrum importer."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.importers.csv_importer import import_csv


def test_import_csv_basic(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("400.0 0.1\n500.0 0.5\n600.0 0.9\n", encoding="utf-8")
    spectrum = import_csv(path, delimiter=" ")
    assert isinstance(spectrum, Spectrum)
    np.testing.assert_array_equal(spectrum.wavelengths, np.array([400.0, 500.0, 600.0]))
    np.testing.assert_array_equal(spectrum.values, np.array([0.1, 0.5, 0.9]))
    assert spectrum.unit == "a.u."
    assert spectrum.meta.get("source_file") == "sample.csv"


def test_import_csv_with_delimiter(tmp_path):
    path = tmp_path / "comma.csv"
    path.write_text("400.0,0.1\n500.0,0.5\n600.0,0.9\n", encoding="utf-8")
    spectrum = import_csv(path, delimiter=",")
    np.testing.assert_array_equal(spectrum.wavelengths, np.array([400.0, 500.0, 600.0]))
    np.testing.assert_array_equal(spectrum.values, np.array([0.1, 0.5, 0.9]))


def test_import_csv_custom_unit(tmp_path):
    path = tmp_path / "unit.csv"
    path.write_text("400.0 0.1\n500.0 0.5\n", encoding="utf-8")
    spectrum = import_csv(path, delimiter=" ", unit="mW/nm")
    assert spectrum.unit == "mW/nm"


def test_import_csv_file_not_found(tmp_path):
    path = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError):
        import_csv(path)


def test_import_csv_not_enough_columns(tmp_path):
    path = tmp_path / "one_col.csv"
    path.write_text("400.0\n500.0\n600.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least two numeric columns"):
        import_csv(path)


def test_import_csv_not_numeric(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("400.0 0.1\n500.0 bad\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least two numeric"):
        import_csv(path)


def test_import_csv_multi_column(tmp_path):
    path = tmp_path / "multi.csv"
    path.write_text(
        "wavelength,R,G,B\n"
        "400.0,0.1,0.2,0.3\n"
        "500.0,0.5,0.6,0.7\n"
        "600.0,0.9,0.8,0.7\n",
        encoding="utf-8",
    )
    result = import_csv(path)
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0].meta.get("name") == "R"
    assert result[0].meta.get("channel") == "R"
    assert result[1].meta.get("name") == "G"
    assert result[2].meta.get("name") == "B"


def test_import_csv_auto_delimiter(tmp_path):
    path = tmp_path / "auto.csv"
    path.write_text("400.0,0.1\n500.0,0.5\n600.0,0.9\n", encoding="utf-8")
    spectrum = import_csv(path, delimiter=None)
    np.testing.assert_array_equal(spectrum.wavelengths, np.array([400.0, 500.0, 600.0]))


def test_import_csv_with_category(tmp_path):
    path = tmp_path / "cat.csv"
    path.write_text(
        "wavelength,R,G\n400.0,0.1,0.2\n500.0,0.5,0.6\n",
        encoding="utf-8",
    )
    result = import_csv(path, default_category="LED")
    assert isinstance(result, list)
    assert result[0].meta.get("category") == "LED"


def test_import_csv_semicolon_delimiter(tmp_path):
    path = tmp_path / "semi.csv"
    path.write_text("400.0;0.1\n500.0;0.5\n", encoding="utf-8")
    spectrum = import_csv(path, delimiter=";")
    np.testing.assert_array_equal(spectrum.wavelengths, np.array([400.0, 500.0]))


def test_import_csv_gcf_channel(tmp_path):
    path = tmp_path / "gcf.csv"
    path.write_text(
        "wavelength,GCF,RCF\n400.0,0.1,0.2\n500.0,0.5,0.6\n",
        encoding="utf-8",
    )
    result = import_csv(path)
    assert isinstance(result, list)
    # GCF channel should be detected from column name
    gcf_spec = [s for s in result if s.meta.get("channel") == "GCF"]
    assert len(gcf_spec) == 1
