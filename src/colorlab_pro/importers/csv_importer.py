"""CSV importer for spectrum data.

Supports two formats:
1. Two-column: wavelength + value
2. Multi-column: wavelength + multiple spectra (header row optional)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from colorlab_pro.dto.spectrum import Spectrum


def _detect_channel_from_name(name: str) -> str | None:
    """Auto-detect channel (R/G/B/RCF/GCF/BCF/W) from column name.

    Uses strict word-boundary matching to avoid false positives like
    "Raw" matching R or "Spectrum" matching nothing.
    """
    import re

    upper = name.upper().strip()

    # Check for CF channels first (RCF/GCF/BCF) — more specific
    if re.search(r"\bRCF\b", upper) or re.search(r"\bR_CF\b", upper):
        return "RCF"
    if re.search(r"\bGCF\b", upper) or re.search(r"\bG_CF\b", upper):
        return "GCF"
    if re.search(r"\bBCF\b", upper) or re.search(r"\bB_CF\b", upper):
        return "BCF"

    # Check for White / WLED
    if re.search(r"\bW(LED)?\b", upper) or "WHITE" in upper:
        return "W"

    # Check for R/G/B as standalone words or suffixes after separator
    # Require R/G/B to be a complete token, not a substring like "Raw"
    if re.search(r"(?:^|[-_ ]|\b)R(?:$|[-_ ]|\b)", upper) or re.search(r"\bRED\b", upper):
        return "R"
    if re.search(r"(?:^|[-_ ]|\b)G(?:$|[-_ ]|\b)", upper) or re.search(r"\bGREEN\b", upper) or re.search(r"\bGRN\b", upper):
        return "G"
    if re.search(r"(?:^|[-_ ]|\b)B(?:$|[-_ ]|\b)", upper) or re.search(r"\bBLUE\b", upper):
        return "B"
    return None


def import_csv(
    path: Path,
    *,
    delimiter: str | None = None,
    unit: str = "a.u.",
    default_category: str | None = None,
) -> Spectrum | list[Spectrum]:
    """Load Spectrum(s) from a CSV/TXT file.

    Args:
        path: Path to the CSV/TXT file.
        delimiter: Column delimiter. Default is auto-detect.
        unit: Unit string for the spectrum values.
        default_category: Force this category on all imported spectra.

    Returns:
        A single Spectrum for 2-column files, or a list for multi-column.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the data cannot be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    # Try to read with headers first
    headers: list[str] = []
    data_array: np.ndarray | None = None

    # Read first line to check for headers
    with open(path) as f:
        first_line = f.readline().strip()

    # Check if first line contains non-numeric values (header)
    # Use comma split for comma-delimited, otherwise use the detected delimiter
    test_sep = ","
    parts = first_line.split(test_sep)
    if len(parts) == 1 and delimiter:
        parts = first_line.split(delimiter)

    try:
        float(parts[0].strip())
        has_header = False
    except (ValueError, IndexError):
        has_header = True

    if delimiter is None:
        for sep in (",", "\t", " "):
            try:
                if has_header:
                    # Skip header row
                    data_array = np.loadtxt(path, delimiter=sep, skiprows=1)
                else:
                    data_array = np.loadtxt(path, delimiter=sep)
                if data_array.ndim == 2 and data_array.shape[1] >= 2:
                    delimiter = sep
                    break
            except (ValueError, TypeError):
                continue
    else:
        if has_header:
            data_array = np.loadtxt(path, delimiter=delimiter, skiprows=1)
        else:
            data_array = np.loadtxt(path, delimiter=delimiter)

    if data_array is None or data_array.ndim != 2 or data_array.shape[1] < 2:
        raise ValueError("File must contain at least two numeric columns.")

    # Parse headers if present
    if has_header:
        with open(path, encoding="utf-8") as f:
            header_line = f.readline().strip()
        sep = delimiter or ","
        headers = [h.strip() for h in header_line.split(sep)]

    wavelengths = data_array[:, 0]
    num_value_cols = data_array.shape[1] - 1

    # Single column — return single Spectrum
    if num_value_cols == 1:
        return Spectrum(
            wavelengths=wavelengths,
            values=data_array[:, 1],
            unit=unit,
            meta={"source_file": str(path.name)},
        )

    # Multi-column — return list of Spectra
    spectra: list[Spectrum] = []
    for col_idx in range(num_value_cols):
        name = headers[col_idx + 1] if col_idx + 1 < len(headers) else f"Spectrum_{col_idx + 1}"
        channel = _detect_channel_from_name(name)

        meta: dict[str, object] = {
            "source_file": str(path.name),
            "name": name,
            "column_index": col_idx,
            "channel": channel,
        }
        if default_category is not None:
            meta["category"] = default_category

        spectra.append(
            Spectrum(
                wavelengths=wavelengths.copy(),
                values=data_array[:, col_idx + 1],
                unit=unit,
                meta=meta,
            )
        )

    return spectra
