"""Input validation helpers for UI/backend payloads."""

from __future__ import annotations

from typing import Any


def validate_xy(value: Any, name: str = "xy") -> tuple[float, float]:
    """Validate and return a CIE 1931 xy coordinate pair."""
    try:
        x, y = float(value[0]), float(value[1])
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{name} must be a pair of numbers") from exc
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError(f"{name} values must be between 0 and 1")
    return x, y


def validate_ratio(value: Any, name: str = "ratio") -> float:
    """Validate a mixing ratio."""
    try:
        ratio = float(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{name} must be a number") from exc
    if ratio < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return ratio


def validate_spectrum_id(value: Any, name: str = "spectrum_id") -> int:
    """Validate a spectrum identifier."""
    try:
        sid = int(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{name} must be an integer") from exc
    if sid <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return sid


def validate_thickness_range(bounds: Any, name: str = "bounds") -> list[list[float]]:
    """Validate thickness bounds as a list of [min, max] pairs."""
    if not isinstance(bounds, list) or len(bounds) != 3:
        raise ValueError(f"{name} must contain exactly 3 [min, max] pairs")
    result: list[list[float]] = []
    for idx, pair in enumerate(bounds):
        try:
            lo, hi = float(pair[0]), float(pair[1])
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{name}[{idx}] must be a [min, max] number pair") from exc
        if lo < 0 or hi < 0:
            raise ValueError(f"{name}[{idx}] thickness values must be non-negative")
        if lo >= hi:
            raise ValueError(f"{name}[{idx}] min must be less than max")
        result.append([lo, hi])
    return result
