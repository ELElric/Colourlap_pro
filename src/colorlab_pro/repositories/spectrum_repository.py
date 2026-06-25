"""Repository for persisting and loading Spectrum DTOs."""

from __future__ import annotations

import json

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from colorlab_pro.database.models import Spectrum as SpectrumORM
from colorlab_pro.database.models import SpectrumPoint
from colorlab_pro.dto.spectrum import Spectrum


def _meta_from_dto(spectrum: Spectrum) -> str | None:
    """Serialize DTO metadata to JSON if non-empty, otherwise None."""
    if spectrum.meta:
        return json.dumps(spectrum.meta, ensure_ascii=False, sort_keys=True)
    return None


def _dto_from_orm(orm: SpectrumORM) -> Spectrum:
    """Build a Spectrum DTO from an ORM instance and its ordered points."""
    wavelengths = np.array([p.wavelength for p in orm.points], dtype=np.float64)
    values = np.array([p.value for p in orm.points], dtype=np.float64)
    meta: dict[str, object] = {}
    if orm.meta_json:
        meta = json.loads(orm.meta_json)
    # Surface category in meta for downstream consumers
    if orm.category and "category" not in meta:
        meta["category"] = orm.category
    return Spectrum(
        wavelengths=wavelengths,
        values=values,
        unit=orm.unit or "a.u.",
        meta=meta,
    )


def _name_from_dto(spectrum: Spectrum, fallback: str | None) -> str:
    """Pick a display name: explicit fallback, then meta['name'], then default."""
    if fallback:
        return fallback
    name = spectrum.meta.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "Untitled"


def save(
    session: Session,
    spectrum: Spectrum,
    project_id: int,
    *,
    name: str | None = None,
    source: str = "import",
    channel: str | None = None,
    category: str | None = None,
) -> int:
    """Persist a Spectrum DTO and return its database id.

    Args:
        session: Active SQLAlchemy ORM session.
        spectrum: Spectrum DTO to persist.
        project_id: Id of the owning project.
        name: Optional display name; inferred from spectrum.meta otherwise.
        source: Provenance string, e.g. "import", "calculated", "optimized".
        channel: Optional channel label.
        category: Optional category label (CF/QD/LED/White/Unknown).

    Returns:
        The generated spectrum id.
    """
    wavelengths = np.asarray(spectrum.wavelengths, dtype=np.float64)
    values = np.asarray(spectrum.values, dtype=np.float64)

    if wavelengths.size == 0:
        wavelength_min = wavelength_max = wavelength_step = None
        fwhm = None
        peak_wavelength = None
    else:
        wavelength_min = float(wavelengths.min())
        wavelength_max = float(wavelengths.max())
        steps = np.diff(wavelengths)
        wavelength_step = float(steps.mean()) if steps.size else None
        # Pre-compute FWHM and peak wavelength at import time so list queries
        # can read them directly without re-computing per spectrum.
        fwhm, peak_wavelength = _compute_fwhm_and_peak(wavelengths, values)

    orm = SpectrumORM(
        project_id=project_id,
        name=_name_from_dto(spectrum, name),
        unit=spectrum.unit,
        source=source,
        channel=channel,
        category=category,
        wavelength_min=wavelength_min,
        wavelength_max=wavelength_max,
        wavelength_step=wavelength_step,
        point_count=len(wavelengths),
        fwhm=fwhm,
        peak_wavelength=peak_wavelength,
        meta_json=_meta_from_dto(spectrum),
    )
    session.add(orm)
    session.flush()  # obtain orm.id

    for idx, (wl, val) in enumerate(zip(wavelengths, values, strict=True)):
        session.add(
            SpectrumPoint(
                spectrum_id=orm.id,
                idx=int(idx),
                wavelength=float(wl),
                value=float(val),
            )
        )

    return int(orm.id)


def get_by_id(session: Session, spectrum_id: int) -> Spectrum | None:
    """Load a Spectrum DTO by id, or None if not found."""
    orm = session.get(SpectrumORM, spectrum_id)
    if orm is None:
        return None
    return _dto_from_orm(orm)


def list_by_project(session: Session, project_id: int) -> list[Spectrum]:
    """Return all spectra belonging to a project, ordered by creation time."""
    orms = session.execute(
        select(SpectrumORM)
        .filter_by(project_id=project_id)
        .order_by(SpectrumORM.created_at)
    ).scalars().all()
    return [_dto_from_orm(orm) for orm in orms]


def delete(session: Session, spectrum_id: int) -> bool:
    """Delete a spectrum and its points. Returns True if it existed."""
    orm = session.get(SpectrumORM, spectrum_id)
    if orm is None:
        return False
    session.delete(orm)
    return True


def find_duplicate(
    session: Session,
    project_id: int,
    wavelengths: np.ndarray,
    values: np.ndarray,
    *,
    category: str | None = None,
) -> int | None:
    """Check if a spectrum with identical data already exists in the project.

    Uses SQL pre-filtering on point_count, wavelength_min, wavelength_max,
    and wavelength_step to avoid loading every spectrum's points into memory.
    Only candidates that pass the cheap SQL filter are loaded for exact
    array comparison.

    If category is provided, prefers matching the category. Returns the id
    of the duplicate if found, None otherwise.
    """
    wavelengths = np.asarray(wavelengths, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)

    if wavelengths.size == 0:
        return None

    wl_min = float(wavelengths.min())
    wl_max = float(wavelengths.max())
    steps = np.diff(wavelengths)
    wl_step = float(steps.mean()) if steps.size else None
    point_count = len(wavelengths)

    # SQL pre-filter: only load spectra with matching structural metadata.
    stmt = (
        select(SpectrumORM)
        .filter(
            SpectrumORM.project_id == project_id,
            SpectrumORM.point_count == point_count,
            SpectrumORM.wavelength_min == wl_min,
            SpectrumORM.wavelength_max == wl_max,
        )
    )
    if wl_step is not None:
        stmt = stmt.filter(SpectrumORM.wavelength_step == wl_step)

    orms = session.execute(stmt).scalars().all()

    best_match: int | None = None

    for orm in orms:
        existing_wl = np.array([p.wavelength for p in orm.points], dtype=np.float64)
        existing_val = np.array([p.value for p in orm.points], dtype=np.float64)

        if existing_wl.shape != wavelengths.shape:
            continue
        if not np.array_equal(existing_wl, wavelengths):
            continue
        if not np.allclose(existing_val, values, rtol=1e-10, atol=1e-12):
            continue

        # Exact match with same category — return immediately
        if category is not None and orm.category == category:
            return int(orm.id)

        # Remember first data match as fallback
        if best_match is None:
            best_match = int(orm.id)

    return best_match


def update_spectrum_fields(
    session: Session,
    spectrum_id: int,
    *,
    channel: str | None = None,
    category: str | None = None,
    name: str | None = None,
) -> bool:
    """Update mutable fields of an existing spectrum. Returns True if updated."""
    orm = session.get(SpectrumORM, spectrum_id)
    if orm is None:
        return False
    updated = False
    if channel is not None and orm.channel != channel:
        orm.channel = channel
        updated = True
    if category is not None and orm.category != category:
        orm.category = category
        updated = True
    if name is not None and orm.name != name:
        orm.name = name
        updated = True
    # Sync meta_json with updated fields
    if updated:
        try:
            meta: dict = json.loads(orm.meta_json) if orm.meta_json else {}
        except (json.JSONDecodeError, TypeError):
            # Corrupt or invalid meta_json — start fresh rather than crash.
            meta: dict = {}
        if channel is not None:
            meta["channel"] = channel
        if category is not None:
            meta["category"] = category
        if name is not None:
            meta["name"] = name
        orm.meta_json = json.dumps(meta, ensure_ascii=False)
    return updated


def _compute_fwhm_and_peak(
    wavelengths: np.ndarray,
    values: np.ndarray,
) -> tuple[float | None, float | None]:
    """Compute FWHM (nm) and peak wavelength (nm) from spectrum data.

    Returns (None, None) if the computation is not applicable (e.g. flat
    or monotonically decreasing spectra with no clear peak).
    """
    if wavelengths.size < 2 or values.size < 2:
        return None, None

    peak_idx = int(np.argmax(values))
    peak_val = float(values[peak_idx])

    # FWHM is only meaningful for emission spectra with a distinct peak.
    # If the peak is at the edge or the spectrum is flat, skip FWHM.
    if peak_idx == 0 or peak_idx == len(values) - 1:
        # Peak at edge — still report peak_wavelength but no FWHM
        return None, float(wavelengths[peak_idx])

    half_max = peak_val / 2.0
    if half_max <= 0:
        return None, float(wavelengths[peak_idx])

    # Search left of peak for the half-max crossing point
    left_wl: float | None = None
    for i in range(peak_idx, 0, -1):
        if values[i] >= half_max >= values[i - 1]:
            # Linear interpolation
            v0, v1 = float(values[i - 1]), float(values[i])
            w0, w1 = float(wavelengths[i - 1]), float(wavelengths[i])
            if v1 != v0:
                frac = (half_max - v0) / (v1 - v0)
                left_wl = w0 + frac * (w1 - w0)
            else:
                left_wl = w1
            break

    # Search right of peak
    right_wl: float | None = None
    for i in range(peak_idx, len(values) - 1):
        if values[i] >= half_max >= values[i + 1]:
            v0, v1 = float(values[i]), float(values[i + 1])
            w0, w1 = float(wavelengths[i]), float(wavelengths[i + 1])
            if v1 != v0:
                frac = (half_max - v0) / (v1 - v0)
                right_wl = w0 + frac * (w1 - w0)
            else:
                right_wl = w1
            break

    if left_wl is not None and right_wl is not None:
        fwhm = right_wl - left_wl
        if fwhm > 0:
            return float(fwhm), float(wavelengths[peak_idx])

    return None, float(wavelengths[peak_idx])
