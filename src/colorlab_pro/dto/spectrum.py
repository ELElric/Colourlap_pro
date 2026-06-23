"""Spectrum DTO."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class Spectrum:
    """Immutable spectrum data transfer object.

    Attributes:
        wavelengths: 1D array of wavelength values in nm (monotonically increasing).
        values: 1D array of intensity values (same length as wavelengths).
        unit: Unit string, e.g. "mW/nm", "counts", "a.u.", "transmittance".
        meta: Free-form metadata dictionary.
    """

    wavelengths: NDArray[np.float64]
    values: NDArray[np.float64]
    unit: str = "a.u."
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.wavelengths.shape != self.values.shape:
            raise ValueError("wavelengths and values must have the same shape")
        if self.wavelengths.ndim != 1:
            raise ValueError("wavelengths must be 1D")
        # Deep-copy meta to prevent external mutation from breaking immutability.
        # Use object.__setattr__ because the dataclass is frozen.
        object.__setattr__(self, "meta", copy.deepcopy(self.meta))
