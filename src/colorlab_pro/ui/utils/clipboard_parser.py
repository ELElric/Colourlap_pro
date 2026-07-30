"""Clipboard spectrum parsing utilities."""

from __future__ import annotations

import math

import numpy as np

from colorlab_pro.dto.spectrum import Spectrum


# Maximum accepted size (in characters) of pasted clipboard text.
MAX_TEXT_SIZE = 1_000_000
# Maximum accepted number of parsed data points.
MAX_PARSE_POINTS = 100_000


def parse_spectrum_from_text(text: str) -> Spectrum:
    """Parse clipboard text into a Spectrum.

    Supports tab, comma, or space delimiters. Auto-detects header row.

    Args:
        text: Raw text copied to the clipboard.

    Returns:
        A Spectrum DTO parsed from the text.

    Raises:
        ValueError: If the text cannot be parsed into a valid spectrum.
    """
    if len(text) > MAX_TEXT_SIZE:
        raise ValueError(
            f"Clipboard text exceeds {MAX_TEXT_SIZE} characters"
        )

    lines = text.strip().splitlines()
    if not lines:
        raise ValueError("Empty clipboard data")

    start_idx = 0
    first = lines[0].strip().lower()
    if any(kw in first for kw in ("nm", "wavelength", "wave", "lambda", "x")):
        start_idx = 1

    wavelengths: list[float] = []
    values: list[float] = []
    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue
        # Stop once we have collected enough points to avoid runaway parsing.
        if len(wavelengths) >= MAX_PARSE_POINTS:
            break
        # Try tab, then comma, then space
        for sep in ("\t", ",", " "):
            parts = line.split(sep)
            if len(parts) >= 2:
                break
        else:
            parts = line.split()
        if len(parts) < 2:
            continue
        try:
            wl = float(parts[0].strip())
            val = float(parts[1].strip())
        except ValueError:
            continue
        # Skip rows with non-finite (NaN/Inf) values.
        if math.isnan(wl) or math.isinf(wl) or math.isnan(val) or math.isinf(val):
            continue
        wavelengths.append(wl)
        values.append(val)

    if len(wavelengths) < 2:
        raise ValueError("Need at least 2 data points")

    return Spectrum(
        wavelengths=np.array(wavelengths, dtype=np.float64),
        values=np.array(values, dtype=np.float64),
        unit="a.u.",
        meta={"name": "Pasted Spectrum", "source": "clipboard"},
    )
