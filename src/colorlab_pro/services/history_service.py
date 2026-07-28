"""HistoryService: save and retrieve calculation session snapshots."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from colorlab_pro.dto.color import XY
from colorlab_pro.dto.history import (
    ChannelSnapshot,
    GamutSnapshot,
    HistorySnapshot,
)
from colorlab_pro.repositories import history_repository


class HistoryService:
    """Service for managing calculation history."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def save_snapshot(self, snapshot: HistorySnapshot) -> int:
        """Save a HistorySnapshot and return its database ID."""
        channels_json = json.dumps(
            [
                {
                    "name": ch.name,
                    "spectrum_id": ch.spectrum_id,
                    "spectrum_name": ch.spectrum_name,
                    "xy_x": ch.xy_x, "xy_y": ch.xy_y,
                    "uv_u": ch.uv_u, "uv_v": ch.uv_v,
                    "peak_wavelength": ch.peak_wavelength,
                    "fwhm": ch.fwhm,
                    "dominant_wavelength": ch.dominant_wavelength,
                    "purity": ch.purity,
                    "cf_name": ch.cf_name,
                    "cf_thickness_um": ch.cf_thickness_um,
                }
                for ch in snapshot.channels
            ],
            ensure_ascii=False,
        ) if snapshot.channels else None

        gamut_json = json.dumps(
            [
                {
                    "standard_name": g.standard_name,
                    "coverage_1931": g.coverage_1931,
                    "coverage_1976": g.coverage_1976,
                    "match_1931": g.match_1931,
                    "match_1976": g.match_1976,
                }
                for g in snapshot.gamut_results
            ],
            ensure_ascii=False,
        ) if snapshot.gamut_results else None

        meta_json = json.dumps(snapshot.meta, ensure_ascii=False) if snapshot.meta else None

        with self._session_factory() as session:
            record = history_repository.create(
                session,
                name=snapshot.name,
                mode=snapshot.mode,
                channels_json=channels_json,
                gamut_results_json=gamut_json,
                target_xy_x=snapshot.target_xy_x,
                target_xy_y=snapshot.target_xy_y,
                achieved_xy_x=snapshot.achieved_xy_x,
                achieved_xy_y=snapshot.achieved_xy_y,
                optimized_thickness_json=snapshot.optimized_thickness_json,
                delta_xy=snapshot.delta_xy,
                meta_json=meta_json,
                project_id=snapshot.project_id,
            )
            session.commit()
            return int(record.id)

    def load_snapshot(self, history_id: int) -> HistorySnapshot | None:
        """Load a HistorySnapshot from the database by ID."""
        with self._session_factory() as session:
            record = history_repository.get_by_id(session, history_id)
            if record is None:
                return None
            return self._record_to_snapshot(record)

    def list_snapshots(
        self, project_id: int | None = None, limit: int = 100
    ) -> list[HistorySnapshot]:
        """List history snapshots, newest first."""
        with self._session_factory() as session:
            records = history_repository.list_all(session, project_id, limit)
            return [self._record_to_snapshot(r) for r in records]

    def rename(self, history_id: int, new_name: str) -> bool:
        """Rename a history record."""
        with self._session_factory() as session:
            result = history_repository.update(session, history_id, name=new_name)
            if result:
                session.commit()
                return True
            return False

    def delete(self, history_id: int) -> bool:
        """Delete a history record."""
        with self._session_factory() as session:
            result = history_repository.delete(session, history_id)
            if result:
                session.commit()
                return True
            return False

    def generate_name(self, mode: str | None = None) -> str:
        """Auto-generate a name based on current date/time."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M")
        if mode:
            mode_labels = {"no_cf": "0um", "cf_fixed": "CF\u56fa\u5b9a", "cf_optimized": "CF\u4f18\u5316"}
            label = mode_labels.get(mode, mode)
            return f"{date_str} ({label})"
        return date_str

    @staticmethod
    def _record_to_snapshot(record) -> HistorySnapshot:
        """Convert a DB History record to a HistorySnapshot DTO."""
        channels = ()
        if record.channels_json:
            try:
                channels = tuple(
                    ChannelSnapshot(**ch) for ch in json.loads(record.channels_json)
                )
            except (json.JSONDecodeError, TypeError):
                pass

        gamut_results = ()
        if record.gamut_results_json:
            try:
                gamut_results = tuple(
                    GamutSnapshot(**g) for g in json.loads(record.gamut_results_json)
                )
            except (json.JSONDecodeError, TypeError):
                pass

        meta = {}
        if record.meta_json:
            try:
                meta = json.loads(record.meta_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return HistorySnapshot(
            name=record.name,
            mode=record.mode,
            channels=channels,
            gamut_results=gamut_results,
            target_xy_x=record.target_xy_x,
            target_xy_y=record.target_xy_y,
            achieved_xy_x=record.achieved_xy_x,
            achieved_xy_y=record.achieved_xy_y,
            optimized_thickness_json=record.optimized_thickness_json,
            delta_xy=record.delta_xy,
            project_id=record.project_id,
            meta=meta,
        )
