"""Global configuration."""

from __future__ import annotations

from pathlib import Path

# Standard wavelength grid
WAVELENGTH_MIN_NM: float = 380.0
WAVELENGTH_MAX_NM: float = 780.0
WAVELENGTH_STEP_NM: int = 1
WAVELENGTH_COUNT: int = 401

# D65 white point (CIE 1931)
D65_XY: tuple[float, float] = (0.3127, 0.3290)

# Project paths (V1.1 hard-coded; will become user-configurable later)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
USER_DATA_DIR: Path = PROJECT_ROOT / "data" / "user"
CACHE_DIR: Path = PROJECT_ROOT / "data" / "cache"
RESOURCE_DIR: Path = PROJECT_ROOT / "resources"
