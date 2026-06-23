"""WhitePointCalculator Engine.

Provides white-point matching for a display system:
- mixing_weights: solve for the per-channel weights that produce a target xy
  from a set of primary spectra (additive mixing).
- nearest_white_point: find the closest standard illuminant / reference xy.
"""

from __future__ import annotations

import numpy as np

from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.spectrum_analyzer import xyz


def mixing_weights(
    primaries: list[Spectrum],
    target_xy: XY,
    normalize: bool = True,
) -> tuple[np.ndarray, XY]:
    """Compute mixing weights to approximate a target white point.

    Solves a constrained least-squares problem:
        minimize |A @ w - b|_2
        subject to w >= 0
    where A is (3, n) with columns = XYZ of each primary
    and b = (X_target, Y_target, Z_target) computed from target_xy with Y=1.

    Args:
        primaries: List of primary spectra (R, G, B, ...).
        target_xy: Desired chromaticity.
        normalize: If True, returned weights sum to 1.0 (relative weights).
            If False, scale for Y_target=1 (absolute).

    Returns:
        (weights, achieved_xy): tuple of numpy weights array and achieved XY.
    """
    if len(primaries) < 2:
        raise ValueError("Need at least two primaries")

    design_matrix = np.zeros((3, len(primaries)), dtype=np.float64)
    for i, s in enumerate(primaries):
        c = xyz(s)
        design_matrix[:, i] = [c.X, c.Y, c.Z]

    # Target XYZ with Y = 1.0
    total = target_xy.x + target_xy.y + (1.0 - target_xy.x - target_xy.y)
    x_t = target_xy.x / total
    y_t = target_xy.y / total
    z_t = (1.0 - target_xy.x - target_xy.y) / total
    b = np.array([x_t, y_t, z_t], dtype=np.float64)

    # Non-negative least squares via scipy.optimize.nnls
    from scipy.optimize import nnls

    w, _ = nnls(design_matrix, b)
    if np.allclose(w, 0):
        raise ValueError("Cannot reach target with non-negative weights")

    if normalize:
        w = w / np.sum(w)

    achieved_xyz = design_matrix @ w
    total_achieved = np.sum(achieved_xyz)
    achieved = XY(
        x=float(achieved_xyz[0] / total_achieved),
        y=float(achieved_xyz[1] / total_achieved),
    )
    return w, achieved


def delta_xy_to_target(
    primaries: list[Spectrum],
    target_xy: XY,
) -> float:
    """Return the delta-xy error after mixing_weights optimization."""
    _, achieved = mixing_weights(primaries, target_xy)
    return float(np.hypot(achieved.x - target_xy.x, achieved.y - target_xy.y))


def nearest_white_point(xy: XY) -> tuple[str, float]:
    """Find the closest standard white point to a given xy.

    Args:
        xy: Input chromaticity.

    Returns:
        (name, distance): name of the nearest standard white point and
        the Euclidean distance in xy.
    """
    refs = {
        "D65": (0.3127, 0.3290),
        "D50": (0.3457, 0.3585),
        "C": (0.3101, 0.3162),
        "A": (0.4476, 0.4074),
        "E": (1.0 / 3.0, 1.0 / 3.0),
    }
    best_name = ""
    best_dist = float("inf")
    for name, (rx, ry) in refs.items():
        d = float(np.hypot(xy.x - rx, xy.y - ry))
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name, best_dist
