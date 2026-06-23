"""Color DTOs: XYZ, XY, Gamut, OptimizationResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class XYZ:
    """CIE 1931 tristimulus values."""

    X: float
    Y: float
    Z: float


@dataclass(frozen=True)
class XY:
    """CIE 1931 chromaticity coordinates."""

    x: float
    y: float

    @classmethod
    def from_xyz(cls, xyz: XYZ) -> XY:
        total = xyz.X + xyz.Y + xyz.Z
        if total == 0:
            raise ValueError("XYZ sum is zero")
        return cls(x=xyz.X / total, y=xyz.Y / total)


@dataclass(frozen=True)
class Gamut:
    """Color gamut defined by primary chromaticities and white point.

    Attributes:
        name: Human-readable label, e.g. "sRGB".
        red: (x, y) of red primary.
        green: (x, y) of green primary.
        blue: (x, y) of blue primary.
        white: (x, y) of white point.
    """

    name: str
    red: tuple[float, float]
    green: tuple[float, float]
    blue: tuple[float, float]
    white: tuple[float, float]


@dataclass(frozen=True)
class OptimizationResult:
    """Result of a thickness optimization."""

    thicknesses_um: tuple[float, ...]  # (d_R, d_G, d_B, ...)
    achieved_xy: XY
    target_xy: XY
    delta_xy: float
    converged: bool
    iterations: int
    meta: dict[str, Any] = field(default_factory=dict)
