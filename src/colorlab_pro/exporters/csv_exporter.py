"""CSV import/export for Spectrum DTOs."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from colorlab_pro.dto.spectrum import Spectrum

__all__ = ["export_spectrum", "import_spectrum"]


def export_spectrum(spectrum: Spectrum, path: Path) -> None:
    """Write a spectrum to a CSV file with wavelength and value columns."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavelength_nm", "value", "unit"])
        for wl, val in zip(spectrum.wavelengths, spectrum.values, strict=True):
            writer.writerow([wl, val, spectrum.unit])


def import_spectrum(path: Path, *, unit: str = "a.u.") -> Spectrum:
    """Read a spectrum from a CSV file.

    The first row is treated as a header. Only the first two numeric columns
    are used (wavelength and value). An explicit ``unit`` overrides the unit
    stored in the file if no unit column exists.
    """
    wavelengths: list[float] = []
    values: list[float] = []
    file_unit = unit

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty") from None

        has_unit = "unit" in [h.strip().lower() for h in header]
        unit_index = next(
            (i for i, h in enumerate(header) if h.strip().lower() == "unit"),
            None,
        )

        for row in reader:
            if not row or not row[0].strip():
                continue
            try:
                wavelengths.append(float(row[0]))
                values.append(float(row[1]))
            except (ValueError, IndexError) as exc:
                raise ValueError(f"Invalid numeric row: {row}") from exc
            if has_unit and unit_index is not None and len(row) > unit_index:
                file_unit = row[unit_index].strip() or unit

    if len(wavelengths) < 2:
        raise ValueError("At least two data points are required")

    return Spectrum(
        wavelengths=np.array(wavelengths, dtype=np.float64),
        values=np.array(values, dtype=np.float64),
        unit=file_unit,
    )
