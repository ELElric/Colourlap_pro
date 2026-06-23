"""Color-related constants shared across layers.

These constants are used by both UI and engine layers to avoid
circular dependencies.
"""

from __future__ import annotations

# UI-friendly Delta E method names that colour-science accepts.
DELTA_E_METHODS: list[str] = [
    "CIE 1976",
    "CIE 1994",
    "CIE 2000",
]

# Supported observers exposed to the UI.
OBSERVER_CHOICES: list[str] = [
    "CIE 1931 2 Degree Standard Observer",
    "CIE 1964 10 Degree Standard Observer",
]

# Supported illuminants exposed to the UI.
ILLUMINANT_CHOICES: list[str] = [
    "A",
    "C",
    "D50",
    "D55",
    "D65",
    "D75",
    "E",
]
