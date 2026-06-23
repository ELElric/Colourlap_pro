"""Unit tests for XLSX exporter/importer."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.exporters.xlsx_exporter import export_spectrum, import_spectrum


@pytest.fixture
def sample_spectrum() -> Spectrum:
    return Spectrum(
        wavelengths=np.array([400.0, 500.0, 600.0]),
        values=np.array([0.1, 0.5, 0.9]),
        unit="mW/nm",
    )


def test_export_import_roundtrip(tmp_path, sample_spectrum):
    path = tmp_path / "spectrum.xlsx"
    export_spectrum(sample_spectrum, path)
    loaded = import_spectrum(path)

    np.testing.assert_array_equal(loaded.wavelengths, sample_spectrum.wavelengths)
    np.testing.assert_array_equal(loaded.values, sample_spectrum.values)
    assert loaded.unit == sample_spectrum.unit
