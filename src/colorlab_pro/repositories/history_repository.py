"""Repository for History CRUD operations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from colorlab_pro.database.models import History


def create(
    session: Session,
    name: str,
    mode: str | None = None,
    channels_json: str | None = None,
    gamut_results_json: str | None = None,
    target_xy_x: float | None = None,
    target_xy_y: float | None = None,
    achieved_xy_x: float | None = None,
    achieved_xy_y: float | None = None,
    optimized_thickness_json: str | None = None,
    delta_xy: float | None = None,
    meta_json: str | None = None,
    project_id: int | None = None,
) -> History:
    """Create a new history record."""
    record = History(
        name=name,
        mode=mode,
        channels_json=channels_json,
        gamut_results_json=gamut_results_json,
        target_xy_x=target_xy_x,
        target_xy_y=target_xy_y,
        achieved_xy_x=achieved_xy_x,
        achieved_xy_y=achieved_xy_y,
        optimized_thickness_json=optimized_thickness_json,
        delta_xy=delta_xy,
        meta_json=meta_json,
        project_id=project_id,
    )
    session.add(record)
    session.flush()
    return record


def get_by_id(session: Session, history_id: int) -> History | None:
    """Get a history record by ID."""
    return session.get(History, history_id)


def list_all(session: Session, project_id: int | None = None, limit: int = 100) -> list[History]:
    """List history records, newest first. Optionally filter by project."""
    stmt = select(History).order_by(History.created_at.desc())
    if project_id is not None:
        stmt = stmt.where(History.project_id == project_id)
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())


def update(session: Session, history_id: int, *, name: str | None = None) -> History | None:
    """Update a history record's name."""
    record = session.get(History, history_id)
    if record is None:
        return None
    if name is not None:
        record.name = name
    record.updated_at = datetime.now(timezone.utc)
    return record


def delete(session: Session, history_id: int) -> bool:
    """Delete a history record."""
    record = session.get(History, history_id)
    if record is None:
        return False
    session.delete(record)
    return True


def count(session: Session, project_id: int | None = None) -> int:
    """Count total history records."""
    stmt = select(func.count()).select_from(History)
    if project_id is not None:
        stmt = stmt.where(History.project_id == project_id)
    return session.execute(stmt).scalar() or 0
