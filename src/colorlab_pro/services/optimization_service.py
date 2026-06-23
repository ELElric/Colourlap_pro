"""OptimizationService orchestrates white-point and thickness optimizations."""

from __future__ import annotations

import json
from collections.abc import Callable

from sqlalchemy.orm import Session

from colorlab_pro.database.models import Optimization
from colorlab_pro.dto.color import XY, OptimizationResult
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.thickness_optimizer import optimize_thickness
from colorlab_pro.engines.white_point_calculator import (
    delta_xy_to_target,
    mixing_weights,
    nearest_white_point,
)


class OptimizationService:
    """Service for white-point mixing and color-filter thickness optimization."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Initialize with a factory that produces SQLAlchemy sessions.

        Args:
            session_factory: Callable returning a new ORM session.
        """
        self._session_factory = session_factory

    def optimize_white_point(
        self,
        primaries: list[Spectrum],
        target_xy: XY,
    ) -> dict[str, object]:
        """Compute per-channel weights to match a target white point.

        Returns a dictionary with keys:
        - ``weights``: list of non-negative weights
        - ``achieved_xy``: achieved XY chromaticity
        - ``delta_xy``: Euclidean error in xy
        - ``nearest_white_point``: name of the nearest standard white point
        """
        weights, achieved_xy = mixing_weights(primaries, target_xy, normalize=True)
        delta_xy = delta_xy_to_target(primaries, target_xy)
        nearest_name, _distance = nearest_white_point(achieved_xy)

        return {
            "weights": [float(w) for w in weights],
            "achieved_xy": achieved_xy,
            "delta_xy": delta_xy,
            "nearest_white_point": nearest_name,
        }

    def optimize_thickness(
        self,
        target_xy: XY,
        source_spectrum: Spectrum,
        absorbers: list[Spectrum],
        bounds_um: tuple[float, float] = (0.1, 10.0),
    ) -> OptimizationResult:
        """Optimize color-filter thicknesses to match a target xy."""
        return optimize_thickness(target_xy, source_spectrum, absorbers, bounds_um=bounds_um)

    def save_optimization(
        self,
        project_id: int,
        name: str,
        target_xy: XY,
        result: OptimizationResult,
    ) -> int:
        """Persist an optimization result and return its id."""
        result_json = json.dumps(
            {
                "thicknesses_um": result.thicknesses_um,
                "achieved_xy": (result.achieved_xy.x, result.achieved_xy.y),
                "target_xy": (result.target_xy.x, result.target_xy.y),
                "delta_xy": result.delta_xy,
                "converged": result.converged,
                "iterations": result.iterations,
                "meta": result.meta,
            },
            ensure_ascii=False,
        )

        with self._session_factory() as session:
            opt = Optimization(
                project_id=project_id,
                name=name,
                target_xy_x=target_xy.x,
                target_xy_y=target_xy.y,
                result_json=result_json,
            )
            session.add(opt)
            session.flush()
            session.commit()
            return int(opt.id)
