"""JSON import/export for Spectrum DTOs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from colorlab_pro.dto.spectrum import Spectrum

__all__ = ["export_spectrum", "import_spectrum"]


def export_spectrum(spectrum: Spectrum, path: Path) -> None:
    """Write a spectrum to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "wavelengths": spectrum.wavelengths.tolist(),
        "values": spectrum.values.tolist(),
        "unit": spectrum.unit,
        "meta": spectrum.meta,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def import_spectrum(path: Path) -> Spectrum:
    """Read a spectrum from a JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return Spectrum(
        wavelengths=np.array(payload["wavelengths"], dtype=np.float64),
        values=np.array(payload["values"], dtype=np.float64),
        unit=payload.get("unit", "a.u."),
        meta=payload.get("meta", {}),
    )
