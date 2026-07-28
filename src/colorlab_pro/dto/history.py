"""HistorySnapshot DTO: immutable record of a calculation session."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChannelSnapshot:
    """Snapshot of a single channel's analysis results."""
    name: str  # "R", "G", "B"
    spectrum_id: int | None  # linked spectrum record, if saved
    spectrum_name: str  # display name
    xy_x: float
    xy_y: float
    uv_u: float
    uv_v: float
    peak_wavelength: float
    fwhm: float
    dominant_wavelength: float | None
    purity: float | None
    # Optional CF filter info
    cf_name: str | None = None
    cf_thickness_um: float | None = None


@dataclass(frozen=True)
class GamutSnapshot:
    """Snapshot of gamut comparison results for one standard."""
    standard_name: str
    coverage_1931: float | None = None
    coverage_1976: float | None = None
    match_1931: float | None = None
    match_1976: float | None = None
    coverage_1931_unit: str = "%"
    coverage_1976_unit: str = "%"
    match_1931_unit: str = "%"
    match_1976_unit: str = "%"


@dataclass(frozen=True)
class HistorySnapshot:
    """Complete snapshot of a calculation session.

    Captures the full state of a calculation including:
    - Channel analysis results (xy, uv, peak, FWHM, DW, purity)
    - Gamut coverage data vs standards
    - Optimization results (thickness, target, achieved)
    - Metadata (mode, CF filter selection)
    """
    name: str  # user-given or auto-generated name
    mode: str  # "no_cf", "cf_fixed", "cf_optimized"
    channels: tuple[ChannelSnapshot, ...] = ()
    gamut_results: tuple[GamutSnapshot, ...] = ()
    # Optimization data (optional)
    target_xy_x: float | None = None
    target_xy_y: float | None = None
    achieved_xy_x: float | None = None
    achieved_xy_y: float | None = None
    optimized_thickness_json: str | None = None  # JSON: {"R": 2.1, "G": 2.7, "B": 2.2}
    delta_xy: float | None = None
    # Metadata
    project_id: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)
