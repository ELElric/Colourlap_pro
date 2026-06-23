"""GamutCalculator Engine.

Provides color gamut analysis (D-016: all in CIE 1931 xy space):
- coverage: device gamut vs target gamut area overlap (xy plane, shapely)
- match: delta-xy based match score (D-017)
- build_gamut_from_primaries: helper to construct a Gamut DTO from primaries
- standard_gamuts: factory for sRGB, DCI-P3, Adobe RGB, NTSC (docs/09 §3)
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import Point, Polygon

from colorlab_pro.dto.color import XY, Gamut

# Standard gamut primaries (D-016: all in xy space)
_GAMUT_SPECS: dict[
    str, tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
] = {
    "sRGB": ((0.6400, 0.3300), (0.3000, 0.6000), (0.1500, 0.0600), (0.3127, 0.3290)),
    "DCI-P3": ((0.6800, 0.3200), (0.2650, 0.6900), (0.1500, 0.0600), (0.3127, 0.3290)),
    "Adobe RGB": ((0.6400, 0.3300), (0.2100, 0.7100), (0.1500, 0.0600), (0.3127, 0.3290)),
    "NTSC": ((0.6700, 0.3300), (0.2100, 0.7100), (0.1400, 0.0800), (0.3100, 0.3160)),
    "BT2020": ((0.7080, 0.2920), (0.1700, 0.7970), (0.1310, 0.0460), (0.3127, 0.3290)),
}


def _xy_to_tuple(xy: XY) -> tuple[float, float]:
    return (xy.x, xy.y)


def xy_to_uv(x: float, y: float) -> tuple[float, float]:
    """Convert CIE 1931 xy chromaticity to CIE 1976 u'v'.

    u' = 4x / (-2x + 12y + 3)
    v' = 9y / (-2x + 12y + 3)
    """
    denom = -2.0 * x + 12.0 * y + 3.0
    if denom == 0:
        return 0.0, 0.0
    return (4.0 * x) / denom, (9.0 * y) / denom


def build_gamut_from_primaries(
    name: str,
    red: XY,
    green: XY,
    blue: XY,
    white: XY,
) -> Gamut:
    """Build a Gamut DTO from red, green, blue and white points."""
    return Gamut(
        name=name,
        red=_xy_to_tuple(red),
        green=_xy_to_tuple(green),
        blue=_xy_to_tuple(blue),
        white=_xy_to_tuple(white),
    )


def standard_gamuts(name: str) -> Gamut:
    """Return a built-in standard gamut by name.

    Supported: sRGB, DCI-P3, Adobe RGB, NTSC.

    Args:
        name: Gamut name.

    Returns:
        Gamut DTO.
    """
    if name not in _GAMUT_SPECS:
        raise ValueError(f"Unknown standard gamut: {name!r}")
    r, g, b, w = _GAMUT_SPECS[name]
    return Gamut(
        name=name,
        red=r,
        green=g,
        blue=b,
        white=w,
    )


def _gamut_to_polygon(gamut: Gamut) -> Polygon:
    """Convert a Gamut to a shapely Polygon (R -> G -> B -> R)."""
    return Polygon([gamut.red, gamut.green, gamut.blue, gamut.red])


def _gamut_to_uv_polygon(gamut: Gamut) -> Polygon:
    """Convert a Gamut to a shapely Polygon in CIE 1976 u'v' space."""
    uv_r = xy_to_uv(*gamut.red)
    uv_g = xy_to_uv(*gamut.green)
    uv_b = xy_to_uv(*gamut.blue)
    return Polygon([uv_r, uv_g, uv_b, uv_r])


def coverage(target: Gamut, device: Gamut) -> float:
    """Compute coverage: device gamut area / target gamut area * 100%.

    Measures how large the device gamut is relative to the target.
    Can exceed 100% when the device gamut is larger than the target.

    Args:
        target: Target gamut (e.g. DCI-P3).
        device: Device gamut (e.g. measured RGB primaries).

    Returns:
        Coverage percentage. May be > 100.0.
    """
    target_poly = _gamut_to_polygon(target)
    device_poly = _gamut_to_polygon(device)
    target_area = target_poly.area
    if target_area == 0:
        raise ValueError("Target gamut has zero area")
    device_area = device_poly.area
    return float(device_area / target_area * 100.0)


def match(target: Gamut, device: Gamut) -> float:
    """Compute match: intersection area / target gamut area * 100%.

    Measures how well the device gamut covers the target gamut.
    Always <= 100.0 (intersection cannot exceed target area).

    Args:
        target: Target gamut.
        device: Device gamut.

    Returns:
        Match percentage [0.0, 100.0].
    """
    target_poly = _gamut_to_polygon(target)
    device_poly = _gamut_to_polygon(device)
    target_area = target_poly.area
    if target_area == 0:
        raise ValueError("Target gamut has zero area")
    intersect_area = target_poly.intersection(device_poly).area
    return float(min(100.0, intersect_area / target_area * 100.0))


def match_spectrum(
    target_spectrum_xy: XY,
    sample_spectrum_xy: XY,
    saturation: float = 0.1,
) -> float:
    """Compute match of a single color (target vs sample) in xy space.

    Args:
        target_spectrum_xy: Target xy.
        sample_spectrum_xy: Sample xy.
        saturation: Delta-xy saturation value (default 0.1).

    Returns:
        Match percentage [0.0, 100.0].
    """
    delta = float(
        np.hypot(
            target_spectrum_xy.x - sample_spectrum_xy.x,
            target_spectrum_xy.y - sample_spectrum_xy.y,
        )
    )
    score = (1.0 - delta / saturation) * 100.0
    return float(max(0.0, min(100.0, score)))


def area(gamut: Gamut) -> float:
    """Return the area of a gamut triangle in xy space."""
    return float(_gamut_to_polygon(gamut).area)


def contains(gamut: Gamut, point: XY) -> bool:
    """Check whether a chromaticity point lies inside or on the boundary of a gamut triangle."""
    return bool(_gamut_to_polygon(gamut).covers(Point(point.x, point.y)))


def coverage_1976(target: Gamut, device: Gamut) -> float:
    """Compute coverage in CIE 1976 u'v' space: device area / target area * 100%."""
    target_poly = _gamut_to_uv_polygon(target)
    device_poly = _gamut_to_uv_polygon(device)
    target_area = target_poly.area
    if target_area == 0:
        raise ValueError("Target gamut has zero area in u'v' space")
    device_area = device_poly.area
    return float(device_area / target_area * 100.0)


def match_1976(target: Gamut, device: Gamut) -> float:
    """Compute match in CIE 1976 u'v' space: intersection area / target area * 100%."""
    target_poly = _gamut_to_uv_polygon(target)
    device_poly = _gamut_to_uv_polygon(device)
    target_area = target_poly.area
    if target_area == 0:
        raise ValueError("Target gamut has zero area in u'v' space")
    intersect_area = target_poly.intersection(device_poly).area
    return float(min(100.0, intersect_area / target_area * 100.0))
