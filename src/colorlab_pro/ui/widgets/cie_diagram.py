"""CIEDiagramWidget -- CIE chromaticity diagram with 1931 xy and 1976 u'v' tabs.

Embeds Matplotlib FigureCanvas in a QTabWidget to display CIE chromaticity
diagrams with spectrum locus, gamut triangles, white point, and dynamic
trajectory overlays.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import colour
import numpy as np
from colour import SpectralShape
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.path import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from colorlab_pro.dto.color import XY

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BG_COLOR = "#1E1E1E"
TEXT_COLOR = "#E0E0E0"

# Standard gamut primaries in CIE 1931 xy
STANDARD_GAMUTS: dict[str, dict[str, tuple[float, float]]] = {
    "sRGB": {
        "R": (0.64, 0.33),
        "G": (0.30, 0.60),
        "B": (0.15, 0.06),
    },
    "NTSC": {
        "R": (0.67, 0.33),
        "G": (0.21, 0.71),
        "B": (0.14, 0.08),
    },
    "DCI-P3": {
        "R": (0.68, 0.32),
        "G": (0.265, 0.69),
        "B": (0.15, 0.06),
    },
    "BT2020": {
        "R": (0.708, 0.292),
        "G": (0.170, 0.797),
        "B": (0.131, 0.046),
    },
}

# Distinct colours for each gamut triangle
GAMUT_COLORS: dict[str, str] = {
    "sRGB": "#4FC3F7",
    "NTSC": "#FF6B6B",
    "DCI-P3": "#4CAF50",
    "BT2020": "#FFC107",
}

# Channel colours for trajectories
CHANNEL_COLORS: dict[str, str] = {
    "R": "#FF4444",
    "G": "#44FF44",
    "B": "#4488FF",
    "White": "#FFFFFF",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hex_to_rgb(hex_color: str) -> np.ndarray:
    """Convert '#RRGGBB' to a normalised RGB ndarray."""
    hex_color = hex_color.lstrip("#")
    return np.array([int(hex_color[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


def _xyz_to_srgb_display(xyz: np.ndarray) -> np.ndarray:
    """将 XYZ 转换为用于显示的 sRGB，并对每个像素按最大通道归一化增强显示效果.

    实现参考项目根目录的 plot_cie_chromaticity.py。
    """
    xyz_arr = np.asarray(xyz)

    # XYZ -> linear sRGB，D65 标准矩阵
    matrix = np.array(
        [
            [3.2406, -1.5372, -0.4986],
            [-0.9689, 1.8758, 0.0415],
            [0.0557, -0.2040, 1.0570],
        ]
    )

    rgb_linear = np.dot(xyz_arr, matrix.T)
    rgb_linear = np.clip(rgb_linear, 0, None)

    max_channel = np.max(rgb_linear, axis=-1, keepdims=True)
    rgb_linear = np.divide(
        rgb_linear,
        max_channel,
        out=np.zeros_like(rgb_linear),
        where=max_channel > 0,
    )

    threshold = 0.0031308
    rgb = np.where(
        rgb_linear <= threshold,
        12.92 * rgb_linear,
        1.055 * np.power(rgb_linear, 1 / 2.4) - 0.055,
    )

    return np.clip(rgb, 0, 1)


def _xy_to_xyz(x: np.ndarray, y: np.ndarray, luminance: float = 1.0) -> np.ndarray:
    """CIE 1931 xyY -> XYZ."""
    y_safe = np.where(y == 0, 1e-10, y)
    x_vals = x * luminance / y_safe
    z_vals = (1 - x - y) * luminance / y_safe
    return np.stack([x_vals, np.full_like(x_vals, luminance), z_vals], axis=-1)


def _xy_to_upvp(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """CIE 1931 xy -> CIE 1976 u'v'."""
    denominator = -2 * x + 12 * y + 3
    denominator = np.where(denominator == 0, 1e-10, denominator)
    up = 4 * x / denominator
    vp = 9 * y / denominator
    return up, vp


def _upvp_to_xy(up: np.ndarray, vp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """CIE 1976 u'v' -> CIE 1931 xy."""
    denominator = 6 * up - 16 * vp + 12
    denominator = np.where(denominator == 0, 1e-10, denominator)
    x = 9 * up / denominator
    y = 4 * vp / denominator
    return x, y


def _xy_to_uv(xy: Sequence[tuple[float, float]]) -> np.ndarray:
    """Convert CIE 1931 xy pairs to CIE 1976 u'v' coordinates.

    Args:
        xy: Iterable of (x, y) tuples.

    Returns:
        Nx2 ndarray of (u', v') values.
    """
    xy_arr = np.asarray(xy, dtype=np.float64)
    x, y = xy_arr[:, 0], xy_arr[:, 1]
    up, vp = _xy_to_upvp(x, y)
    return np.column_stack([up, vp])


_SPECTRUM_LOCUS_CACHE: tuple[np.ndarray, np.ndarray] | None = None


def _compute_spectrum_locus_xy() -> tuple[np.ndarray, np.ndarray]:
    """Compute the spectrum locus using colour-science CMF data.

    The result is cached because the locus only depends on the standard observer.

    Returns:
        (xy_locus, wavelengths) -- Nx2 xy array and 1-D wavelength array.
    """
    global _SPECTRUM_LOCUS_CACHE
    if _SPECTRUM_LOCUS_CACHE is not None:
        return _SPECTRUM_LOCUS_CACHE

    cmfs = colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"]
    cmfs = cmfs.copy().align(SpectralShape(380, 780, 1))
    wavelengths = cmfs.wavelengths
    xyz_cmfs = cmfs.values

    total = xyz_cmfs.sum(axis=1)
    total = np.where(total == 0, 1e-10, total)
    xy = xyz_cmfs[:, :2] / total[:, None]
    _SPECTRUM_LOCUS_CACHE = (xy, wavelengths)
    return _SPECTRUM_LOCUS_CACHE


def _style_axis(ax, xlabel: str, ylabel: str, title: str) -> None:
    """Apply dark-theme styling to a Matplotlib axes."""
    ax.set_facecolor(BG_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=8)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_color(TEXT_COLOR)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=10, pad=6)
    ax.grid(True, color="#3A3A3A", linewidth=0.5, linestyle="-", alpha=0.6)


# ---------------------------------------------------------------------------
# CIE Diagram Canvas (single tab)
# ---------------------------------------------------------------------------


class CIECanvas(FigureCanvas):
    """Matplotlib canvas that renders one CIE chromaticity diagram.

    Parameters
    ----------
    mode : str
        ``'xy'`` for CIE 1931 or ``'uv'`` for CIE 1976.
    """

    def __init__(self, mode: str = "xy", parent: QWidget | None = None) -> None:
        self._figure = Figure(figsize=(5, 5), dpi=100)
        self._figure.patch.set_facecolor(BG_COLOR)
        self._figure.subplots_adjust(left=0.10, right=0.95, top=0.93, bottom=0.10)
        super().__init__(self._figure)
        self.setParent(parent)

        self._mode = mode
        self._ax = self._figure.add_subplot(111)

        # Spectrum locus data
        self._locus_xy: np.ndarray | None = None
        self._locus_uv: np.ndarray | None = None

        # User data
        self._original_rgb_xy: list[tuple[float, float]] | None = None
        self._filtered_rgb_xy: list[tuple[float, float]] | None = None
        self._white_xy: tuple[float, float] | None = None
        self._filtered_white_xy: tuple[float, float] | None = None
        self._trajectories: dict[str, list[tuple[float, float]]] = {}
        self._reference_gamuts: list[str] = []

        # Extra metadata for hover (peak wavelength, purity)
        self._original_meta: list[dict] = [{}, {}, {}]
        self._filtered_meta: list[dict] = [{}, {}, {}]

        # Visibility flags
        self._show_original = True
        self._show_filtered = True
        self._show_white_point = True
        self._show_trajectory = True
        self._show_triangle = True

        # Hover annotation
        self._annotation = self._ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            fontsize=8,
            color=TEXT_COLOR,
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": "#2A2A2A",
                "edgecolor": "#555555",
                "alpha": 0.9,
            },
            arrowprops={"arrowstyle": "->", "color": "#888888"},
            visible=False,
        )

        # Cache for expensive static background
        self._bg_cache: dict[str, dict] = {}

        # Connect events
        self.mpl_connect("motion_notify_event", self._on_motion)

        self._draw_base()

    # ----- public API (mirrors widget) -----

    def set_original_rgb(
        self,
        r_xy: tuple[float, float],
        g_xy: tuple[float, float],
        b_xy: tuple[float, float],
        white_xy: tuple[float, float] | None = None,
        *,
        r_meta: dict | None = None,
        g_meta: dict | None = None,
        b_meta: dict | None = None,
    ) -> None:
        self._original_rgb_xy = [r_xy, g_xy, b_xy]
        self._white_xy = white_xy
        self._original_meta = [
            r_meta or {},
            g_meta or {},
            b_meta or {},
        ]

    def set_filtered_rgb(
        self,
        r_xy: tuple[float, float],
        g_xy: tuple[float, float],
        b_xy: tuple[float, float],
        white_xy: tuple[float, float] | None = None,
        *,
        r_meta: dict | None = None,
        g_meta: dict | None = None,
        b_meta: dict | None = None,
    ) -> None:
        self._filtered_rgb_xy = [r_xy, g_xy, b_xy]
        self._filtered_white_xy = white_xy
        self._filtered_meta = [
            r_meta or {},
            g_meta or {},
            b_meta or {},
        ]

    def add_trajectory_point(self, channel: str, xy: tuple[float, float]) -> None:
        self._trajectories.setdefault(channel, []).append(xy)

    def clear_trajectories(self) -> None:
        self._trajectories.clear()

    def set_reference_gamuts(self, gamut_names: list[str]) -> None:
        self._reference_gamuts = list(gamut_names)

    def set_show_original(self, show: bool) -> None:
        self._show_original = show

    def set_show_filtered(self, show: bool) -> None:
        self._show_filtered = show

    def set_show_white_point(self, show: bool) -> None:
        self._show_white_point = show

    def set_show_trajectory(self, show: bool) -> None:
        self._show_trajectory = show

    def set_show_triangle(self, show: bool) -> None:
        self._show_triangle = show

    def refresh(self) -> None:
        self._draw_base()

    def clear_all(self) -> None:
        self._original_rgb_xy = None
        self._filtered_rgb_xy = None
        self._white_xy = None
        self._filtered_white_xy = None
        self._trajectories.clear()
        self._reference_gamuts.clear()
        self._draw_base()

    # ----- drawing -----

    def _draw_base(self) -> None:
        """Full redraw of the diagram."""
        ax = self._ax
        ax.clear()

        # Draw chromaticity background (horseshoe + colour fill) using colour-science
        self._draw_colour_background()

        if self._mode == "xy":
            _style_axis(ax, "x", "y", "CIE 1931 xy")
            ax.set_xlim(0.0, 0.8)
            ax.set_ylim(0.0, 0.9)
        else:
            _style_axis(ax, "u'", "v'", "CIE 1976 u'v'")
            ax.set_xlim(0.0, 0.65)
            ax.set_ylim(0.0, 0.65)

        self._draw_reference_gamuts()
        self._draw_user_triangle()
        self._draw_original_points()
        self._draw_filtered_points()
        self._draw_white_points()
        self._draw_trajectories()

        # Re-create annotation after clear
        self._annotation = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            fontsize=8,
            color=TEXT_COLOR,
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": "#2A2A2A",
                "edgecolor": "#555555",
                "alpha": 0.9,
            },
            arrowprops={"arrowstyle": "->", "color": "#888888"},
            visible=False,
        )

        self.draw()

    def _compute_xy_background(self, resolution: int) -> dict:
        """Compute and cache the static xy background image and locus data."""
        x_min, x_max = 0.0, 0.8
        y_min, y_max = 0.0, 0.9
        x = np.linspace(x_min, x_max, resolution)
        y = np.linspace(y_min, y_max, resolution)
        x_grid, y_grid = np.meshgrid(x, y)
        xyz = _xy_to_xyz(x_grid, y_grid, luminance=1.0)
        rgb = _xyz_to_srgb_display(xyz)

        locus_xy, wavelengths = _compute_spectrum_locus_xy()
        polygon = np.vstack([locus_xy, locus_xy[0:1]])
        points = np.column_stack([x_grid.ravel(), y_grid.ravel()])
        mask = Path(polygon).contains_points(points).reshape(resolution, resolution)

        image = np.full_like(rgb, _hex_to_rgb(BG_COLOR))
        image[mask] = rgb[mask]

        return {
            "image": image,
            "locus": locus_xy,
            "wavelengths": wavelengths,
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
        }

    def _compute_uv_background(self, resolution: int) -> dict:
        """Compute and cache the static uv background image and locus data."""
        u_min, u_max = 0.0, 0.65
        v_min, v_max = 0.0, 0.65
        u = np.linspace(u_min, u_max, resolution)
        v = np.linspace(v_min, v_max, resolution)
        u_grid, v_grid = np.meshgrid(u, v)
        x, y = _upvp_to_xy(u_grid, v_grid)
        xyz = _xy_to_xyz(x, y, luminance=1.0)
        rgb = _xyz_to_srgb_display(xyz)

        locus_xy, wavelengths = _compute_spectrum_locus_xy()
        locus_uv = _xy_to_uv(locus_xy)
        polygon = np.vstack([locus_uv, locus_uv[0:1]])
        points = np.column_stack([u_grid.ravel(), v_grid.ravel()])
        mask = Path(polygon).contains_points(points).reshape(resolution, resolution)

        image = np.full_like(rgb, _hex_to_rgb(BG_COLOR))
        image[mask] = rgb[mask]

        return {
            "image": image,
            "locus": locus_uv,
            "wavelengths": wavelengths,
            "u_min": u_min,
            "u_max": u_max,
            "v_min": v_min,
            "v_max": v_max,
        }

    def _draw_colour_background(self) -> None:
        """Draw the horseshoe and colour fill using cached static data.

        The background only depends on the diagram mode and resolution, so it is
        computed once and reused across refreshes.
        """
        ax = self._ax
        resolution = 200  # reduced from 500 for better interactivity

        cached = self._bg_cache.get(self._mode)
        if cached is None:
            if self._mode == "xy":
                cached = self._compute_xy_background(resolution)
            else:
                cached = self._compute_uv_background(resolution)
            self._bg_cache[self._mode] = cached

        if self._mode == "xy":
            ax.imshow(
                cached["image"],
                origin="lower",
                extent=[
                    cached["x_min"],
                    cached["x_max"],
                    cached["y_min"],
                    cached["y_max"],
                ],
                aspect="auto",
                zorder=0,
            )

            locus = cached["locus"]
            ax.plot(
                locus[:, 0],
                locus[:, 1],
                color=TEXT_COLOR,
                linewidth=1.0,
                zorder=1,
            )
            ax.plot(
                [locus[0, 0], locus[-1, 0]],
                [locus[0, 1], locus[-1, 1]],
                color=TEXT_COLOR,
                linewidth=1.0,
                zorder=1,
            )

            for wl in range(420, 701, 40):
                idx = int(np.argmin(np.abs(cached["wavelengths"] - wl)))
                x_pos, y_pos = locus[idx]
                ax.text(
                    x_pos,
                    y_pos,
                    str(wl),
                    color=TEXT_COLOR,
                    fontsize=7,
                    ha="center",
                    va="bottom",
                    zorder=4,
                )
        else:
            ax.imshow(
                cached["image"],
                origin="lower",
                extent=[
                    cached["u_min"],
                    cached["u_max"],
                    cached["v_min"],
                    cached["v_max"],
                ],
                aspect="auto",
                zorder=0,
            )

            locus = cached["locus"]
            ax.plot(
                locus[:, 0],
                locus[:, 1],
                color=TEXT_COLOR,
                linewidth=1.0,
                zorder=1,
            )
            ax.plot(
                [locus[0, 0], locus[-1, 0]],
                [locus[0, 1], locus[-1, 1]],
                color=TEXT_COLOR,
                linewidth=1.0,
                zorder=1,
            )

            for wl in range(420, 701, 40):
                idx = int(np.argmin(np.abs(cached["wavelengths"] - wl)))
                u_pos, v_pos = locus[idx]
                ax.text(
                    u_pos,
                    v_pos,
                    str(wl),
                    color=TEXT_COLOR,
                    fontsize=7,
                    ha="center",
                    va="bottom",
                    zorder=4,
                )

    def _get_locus(self) -> np.ndarray:
        """Return locus in the current coordinate system."""
        if self._locus_xy is None:
            self._locus_xy, _ = _compute_spectrum_locus_xy()
            self._locus_uv = _xy_to_uv(self._locus_xy)
        return self._locus_uv if self._mode == "uv" else self._locus_xy

    def _convert(self, xy: Sequence[tuple[float, float] | XY]) -> np.ndarray:
        """Convert xy to the current mode coordinates.

        Supports both plain (x, y) tuples and colour-science ``XY`` objects.
        """
        converted: list[tuple[float, float]] = []
        for item in xy:
            if isinstance(item, tuple):
                converted.append(item)
            else:
                converted.append((float(item.x), float(item.y)))
        arr = np.asarray(converted, dtype=np.float64)
        if self._mode == "uv":
            return _xy_to_uv(arr)
        return arr

    def _draw_reference_gamuts(self) -> None:
        """Draw selected standard gamut triangles."""
        for name in self._reference_gamuts:
            if name not in STANDARD_GAMUTS:
                continue
            gamut = STANDARD_GAMUTS[name]
            pts_xy = [gamut["R"], gamut["G"], gamut["B"], gamut["R"]]
            pts = self._convert(pts_xy)
            color = GAMUT_COLORS.get(name, "#FFFFFF")
            self._ax.fill(
                pts[:, 0],
                pts[:, 1],
                alpha=0.08,
                color=color,
                zorder=1,
            )
            self._ax.plot(
                pts[:, 0],
                pts[:, 1],
                color=color,
                linewidth=1.0,
                linestyle="--",
                alpha=0.6,
                zorder=1,
                label=name,
            )

        if self._reference_gamuts:
            self._ax.legend(
                loc="upper right",
                fontsize=7,
                facecolor="#2A2A2A",
                edgecolor="#555555",
                labelcolor=TEXT_COLOR,
                framealpha=0.85,
            )

    def _draw_user_triangle(self) -> None:
        """Draw the user RGB triangle (from filtered coordinates if available)."""
        if not self._show_triangle:
            return
        pts_xy = self._filtered_rgb_xy or self._original_rgb_xy
        if pts_xy is None:
            return
        tri_xy = list(pts_xy) + [pts_xy[0]]
        pts = self._convert(tri_xy)
        self._ax.fill(
            pts[:, 0],
            pts[:, 1],
            alpha=0.15,
            color="#FFFFFF",
            zorder=4,
        )
        self._ax.plot(
            pts[:, 0],
            pts[:, 1],
            color="#FFFFFF",
            linewidth=1.2,
            linestyle="-",
            alpha=0.7,
            zorder=4,
        )

    def _draw_original_points(self) -> None:
        """Draw original RGB coordinates as hollow circles."""
        if not self._show_original or self._original_rgb_xy is None:
            return
        pts = self._convert(self._original_rgb_xy)
        colors = ["#FF4444", "#44FF44", "#4488FF"]
        labels = ["R", "G", "B"]
        for _i, (pt, c, lbl) in enumerate(zip(pts, colors, labels, strict=True)):
            self._ax.plot(
                pt[0],
                pt[1],
                "o",
                markersize=8,
                markerfacecolor="none",
                markeredgecolor=c,
                markeredgewidth=1.8,
                zorder=6,
            )
            self._ax.annotate(
                lbl,
                (pt[0], pt[1]),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=7,
                color=c,
                zorder=7,
            )

    def _draw_filtered_points(self) -> None:
        """Draw filtered RGB coordinates as filled circles."""
        if not self._show_filtered or self._filtered_rgb_xy is None:
            return
        pts = self._convert(self._filtered_rgb_xy)
        colors = ["#FF4444", "#44FF44", "#4488FF"]
        labels = ["R'", "G'", "B'"]
        for _i, (pt, c, lbl) in enumerate(zip(pts, colors, labels, strict=True)):
            self._ax.plot(
                pt[0],
                pt[1],
                "o",
                markersize=7,
                markerfacecolor=c,
                markeredgecolor="white",
                markeredgewidth=0.8,
                zorder=6,
            )
            self._ax.annotate(
                lbl,
                (pt[0], pt[1]),
                textcoords="offset points",
                xytext=(6, -8),
                fontsize=7,
                color=c,
                zorder=7,
            )

    def _draw_white_points(self) -> None:
        """Draw white point markers."""
        if not self._show_white_point:
            return
        if self._white_xy is not None:
            pt = self._convert([self._white_xy])[0]
            self._ax.plot(
                pt[0],
                pt[1],
                marker="+",
                markersize=12,
                markeredgewidth=2,
                color="#FFFFFF",
                zorder=6,
            )
            self._ax.annotate(
                "W",
                (pt[0], pt[1]),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
                color="#FFFFFF",
                fontweight="bold",
                zorder=7,
            )
        if self._filtered_white_xy is not None:
            pt = self._convert([self._filtered_white_xy])[0]
            self._ax.plot(
                pt[0],
                pt[1],
                marker="x",
                markersize=10,
                markeredgewidth=2,
                color="#AAAAAA",
                zorder=6,
            )
            self._ax.annotate(
                "W'",
                (pt[0], pt[1]),
                textcoords="offset points",
                xytext=(6, -10),
                fontsize=7,
                color="#AAAAAA",
                zorder=7,
            )

    def _draw_trajectories(self) -> None:
        """Draw dynamic trajectory lines for each channel."""
        if not self._show_trajectory:
            return
        for channel, points_xy in self._trajectories.items():
            if len(points_xy) < 2:
                continue
            pts = self._convert(points_xy)
            color = CHANNEL_COLORS.get(channel, "#FFFFFF")
            self._ax.plot(
                pts[:, 0],
                pts[:, 1],
                linestyle="--",
                linewidth=1.2,
                color=color,
                alpha=0.8,
                zorder=5,
                label=f"{channel} trajectory",
            )
            # Draw the last point as a small dot
            self._ax.plot(
                pts[-1, 0],
                pts[-1, 1],
                "o",
                markersize=4,
                color=color,
                zorder=5,
            )

    # ----- mouse hover -----

    def _on_motion(self, event) -> None:
        """Handle mouse motion for hover annotation."""
        if event.inaxes != self._ax or event.xdata is None:
            self._annotation.set_visible(False)
            self.draw_idle()
            return

        x, y = event.xdata, event.ydata
        # Check if mouse is near any RGB point and show Peak/Purity
        nearest_info = self._find_nearest_rgb_point(x, y)
        if self._mode == "xy":
            text = f"x = {x:.3f}\ny = {y:.3f}"
        else:
            text = f"u' = {x:.3f}\nv' = {y:.3f}"
        if nearest_info:
            text += f"\n{nearest_info}"

        self._annotation.set_text(text)
        self._annotation.xy = (x, y)
        self._annotation.set_visible(True)
        self.draw_idle()

    def _find_nearest_rgb_point(self, x: float, y: float) -> str | None:
        """Find nearest RGB point and return its Peak/Purity info."""
        threshold = 0.03
        labels = ["R", "G", "B"]
        for idx, label in enumerate(labels):
            px, py = None, None
            if self._show_filtered and self._filtered_rgb_xy:
                px, py = self._filtered_rgb_xy[idx]
            elif self._show_original and self._original_rgb_xy:
                px, py = self._original_rgb_xy[idx]
            if px is None:
                continue
            if self._mode == "uv":
                denom = -2 * px + 12 * py + 3
                if denom != 0:
                    px, py = 4 * px / denom, 9 * py / denom
            dist = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if dist < threshold:
                meta = self._filtered_meta[idx] if self._show_filtered else self._original_meta[idx]
                peak = meta.get("peak")
                purity = meta.get("purity")
                parts = [label]
                if peak is not None:
                    parts.append(f"Peak={peak:.0f}nm")
                if purity is not None:
                    parts.append(f"Purity={purity:.3f}")
                return "  ".join(parts)
        return None


# ---------------------------------------------------------------------------
# Main Widget
# ---------------------------------------------------------------------------


class CIEDiagramWidget(QWidget):
    """CIE chromaticity diagram widget with two tabs (1931 xy and 1976 u'v').

    Signals
    -------
    locus_ready : Signal
        Emitted after the spectrum locus has been computed.
    """

    locus_ready = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QTabWidget(self)
        layout.addWidget(self._tab_widget)

        self._canvas_xy = CIECanvas(mode="xy", parent=self._tab_widget)
        self._canvas_uv = CIECanvas(mode="uv", parent=self._tab_widget)

        self._tab_widget.addTab(self._canvas_xy, "CIE 1931 xy")
        self._tab_widget.addTab(self._canvas_uv, "CIE 1976 u'v'")

        # Pre-compute locus data for both canvases
        self._canvas_xy._get_locus()
        self._canvas_uv._get_locus()
        self.locus_ready.emit()

    # ----- public API -----

    def set_original_rgb(
        self,
        r_xy: tuple[float, float],
        g_xy: tuple[float, float],
        b_xy: tuple[float, float],
        white_xy: tuple[float, float] | None = None,
    ) -> None:
        """Set the original (unfiltered) RGB primary coordinates.

        Args:
            r_xy: (x, y) for red primary.
            g_xy: (x, y) for green primary.
            b_xy: (x, y) for blue primary.
            white_xy: Optional (x, y) for white point.
        """
        self._canvas_xy.set_original_rgb(r_xy, g_xy, b_xy, white_xy)
        self._canvas_uv.set_original_rgb(r_xy, g_xy, b_xy, white_xy)

    def set_filtered_rgb(
        self,
        r_xy: tuple[float, float],
        g_xy: tuple[float, float],
        b_xy: tuple[float, float],
        white_xy: tuple[float, float] | None = None,
    ) -> None:
        """Set the filtered (corrected) RGB primary coordinates.

        Args:
            r_xy: (x, y) for red primary.
            g_xy: (x, y) for green primary.
            b_xy: (x, y) for blue primary.
            white_xy: Optional (x, y) for white point.
        """
        self._canvas_xy.set_filtered_rgb(r_xy, g_xy, b_xy, white_xy)
        self._canvas_uv.set_filtered_rgb(r_xy, g_xy, b_xy, white_xy)

    def add_trajectory_point(self, channel: str, xy: tuple[float, float]) -> None:
        """Add a trajectory point for a specific channel.

        Args:
            channel: One of ``'R'``, ``'G'``, ``'B'``, ``'White'``.
            xy: (x, y) coordinate of the point.
        """
        self._canvas_xy.add_trajectory_point(channel, xy)
        self._canvas_uv.add_trajectory_point(channel, xy)
        # Limit trajectory length to prevent unbounded memory growth
        max_points = 200
        for canvas in (self._canvas_xy, self._canvas_uv):
            for _ch, pts in canvas._trajectories.items():
                if len(pts) > max_points:
                    del pts[: len(pts) - max_points]

    def clear_trajectories(self) -> None:
        """Clear all trajectory data."""
        self._canvas_xy.clear_trajectories()
        self._canvas_uv.clear_trajectories()

    def set_reference_gamuts(self, gamut_names: list[str]) -> None:
        """Set which standard gamut triangles to display.

        Args:
            gamut_names: List of gamut names (``'sRGB'``, ``'NTSC'``,
                ``'DCI-P3'``, ``'BT2020'``).
        """
        self._canvas_xy.set_reference_gamuts(gamut_names)
        self._canvas_uv.set_reference_gamuts(gamut_names)

    def set_show_original(self, show: bool) -> None:
        """Show or hide original RGB coordinate markers."""
        self._canvas_xy.set_show_original(show)
        self._canvas_uv.set_show_original(show)

    def set_show_filtered(self, show: bool) -> None:
        """Show or hide filtered RGB coordinate markers."""
        self._canvas_xy.set_show_filtered(show)
        self._canvas_uv.set_show_filtered(show)

    def set_show_white_point(self, show: bool) -> None:
        """Show or hide the white point marker."""
        self._canvas_xy.set_show_white_point(show)
        self._canvas_uv.set_show_white_point(show)

    def set_show_trajectory(self, show: bool) -> None:
        """Show or hide dynamic trajectory lines."""
        self._canvas_xy.set_show_trajectory(show)
        self._canvas_uv.set_show_trajectory(show)

    def set_show_triangle(self, show: bool) -> None:
        """Show or hide the user RGB triangle."""
        self._canvas_xy.set_show_triangle(show)
        self._canvas_uv.set_show_triangle(show)

    def refresh(self) -> None:
        """Redraw both diagrams."""
        self._canvas_xy.refresh()
        self._canvas_uv.refresh()

    def clear(self) -> None:
        """Clear all user data and redraw."""
        self._canvas_xy.clear_all()
        self._canvas_uv.clear_all()
