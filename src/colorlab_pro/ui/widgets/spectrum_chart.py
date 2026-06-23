"""SpectrumChartWidget — matplotlib-based spectrum plot widget.

Embeds a Matplotlib FigureCanvas in a QWidget for displaying
spectral distribution curves.
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PySide6.QtWidgets import QVBoxLayout, QWidget

from colorlab_pro.dto.spectrum import Spectrum


class SpectrumChartWidget(QWidget):
    """Widget for plotting one or more spectra.

    Uses Matplotlib with a dark theme to match the application style.
    Supports mouse-wheel zoom, box-select zoom, double-click reset,
    and hover tooltips showing wavelength/intensity at the cursor.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the chart widget."""
        super().__init__(parent)
        # Track plotted curves for hover tooltips: list of (label, color, wavelengths, values)
        self._curves: list[tuple[str, str, np.ndarray, np.ndarray]] = []
        self._tooltip_annotation = None
        self._build_ui()
        self._connect_events()

    def _build_ui(self) -> None:
        """Create the matplotlib figure and canvas."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(figsize=(6, 3), dpi=100)
        self._figure.patch.set_facecolor("#1E1E1E")
        # Reserve enough bottom margin so xlabel + tick labels are not clipped.
        self._figure.subplots_adjust(left=0.10, right=0.95, top=0.90, bottom=0.15)
        self._canvas = FigureCanvas(self._figure)
        layout.addWidget(self._canvas)

        self._ax = self._figure.add_subplot(111)
        self._ax.set_facecolor("#1E1E1E")
        self._ax.tick_params(colors="#E0E0E0")
        self._ax.xaxis.label.set_color("#E0E0E0")
        self._ax.yaxis.label.set_color("#E0E0E0")
        self._ax.title.set_color("#E0E0E0")
        self._ax.spines["bottom"].set_color("#E0E0E0")
        self._ax.spines["top"].set_color("#E0E0E0")
        self._ax.spines["left"].set_color("#E0E0E0")
        self._ax.spines["right"].set_color("#E0E0E0")

        self._ax.set_xlabel("Wavelength (nm)")
        self._ax.set_ylabel("Intensity")
        self._ax.set_title("Spectrum")

        self._orig_xlim: tuple[float, float] | None = None
        self._orig_ylim: tuple[float, float] | None = None
        self._drag_start: tuple[float, float] | None = None
        self._drag_rect: Rectangle | None = None

    def _connect_events(self) -> None:
        """Connect matplotlib mouse events for zoom, reset, and hover."""
        self._canvas.mpl_connect("scroll_event", self._on_scroll)
        self._canvas.mpl_connect("button_press_event", self._on_press)
        self._canvas.mpl_connect("button_release_event", self._on_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._canvas.mpl_connect("axes_leave_event", self._hide_tooltip)

    def _store_orig_limits(self) -> None:
        """Store the original data limits for reset."""
        if self._orig_xlim is None:
            self._orig_xlim = self._ax.get_xlim()
        if self._orig_ylim is None:
            self._orig_ylim = self._ax.get_ylim()

    def plot_spectrum(
        self,
        spectrum: Spectrum,
        *,
        label: str | None = None,
        color: str | None = None,
    ) -> None:
        """Plot a single spectrum.

        Args:
            spectrum: The spectrum to plot.
            label: Optional legend label.
            color: Optional line color.
        """
        lbl = label or "Spectrum"
        clr = color or "#4FC3F7"
        self._ax.plot(
            spectrum.wavelengths,
            spectrum.values,
            label=lbl,
            color=clr,
        )
        self._curves.append((lbl, clr, spectrum.wavelengths, spectrum.values))
        self._ax.legend(facecolor="#1E1E1E", edgecolor="#E0E0E0", labelcolor="#E0E0E0")
        self._store_orig_limits()
        self._canvas.draw()

    def plot_multiple(self, spectra: list[Spectrum], labels: list[str] | None = None) -> None:
        """Plot multiple spectra with distinct colors.

        Args:
            spectra: List of spectra to plot.
            labels: Optional legend labels.
        """
        colors = ["#4FC3F7", "#FF6B6B", "#4CAF50", "#FFC107", "#9C27B0", "#FF9800"]
        for i, spec in enumerate(spectra):
            label = (labels or [])[i] if labels and i < len(labels) else f"Spectrum {i + 1}"
            color = colors[i % len(colors)]
            self._ax.plot(spec.wavelengths, spec.values, label=label, color=color)
        self._ax.legend(facecolor="#1E1E1E", edgecolor="#E0E0E0", labelcolor="#E0E0E0")
        self._store_orig_limits()
        self._canvas.draw()

    def plot_spectra(
        self,
        spectra: list[tuple[Spectrum, str, str]],
        *,
        draw: bool = True,
    ) -> None:
        """Plot multiple spectra in one shot with explicit labels and colors.

        Args:
            spectra: List of (spectrum, label, color) tuples.
            draw: Whether to redraw the canvas immediately. Set to False when
                calling this method multiple times in a row and call draw() once
                at the end.
        """
        for spec, label, color in spectra:
            self._ax.plot(
                spec.wavelengths,
                spec.values,
                label=label,
                color=color,
            )
            self._curves.append((label, color, spec.wavelengths, spec.values))
        self._ax.legend(facecolor="#1E1E1E", edgecolor="#E0E0E0", labelcolor="#E0E0E0")
        self._store_orig_limits()
        if draw:
            self._canvas.draw()

    def draw(self) -> None:  # noqa: A003
        """Redraw the canvas."""
        self._canvas.draw()

    def clear(self) -> None:
        """Clear all plotted data."""
        self._ax.clear()
        self._ax.set_facecolor("#1E1E1E")
        self._ax.tick_params(colors="#E0E0E0")
        self._ax.xaxis.label.set_color("#E0E0E0")
        self._ax.yaxis.label.set_color("#E0E0E0")
        self._ax.title.set_color("#E0E0E0")
        for spine in self._ax.spines.values():
            spine.set_color("#E0E0E0")
        self._ax.set_xlabel("Wavelength (nm)")
        self._ax.set_ylabel("Intensity")
        self._ax.set_title("Spectrum")
        self._orig_xlim = None
        self._orig_ylim = None
        self._drag_start = None
        self._drag_rect = None
        self._curves = []
        self._tooltip_annotation = None
        self._canvas.draw()

    def _on_scroll(self, event) -> None:
        """Zoom with the mouse wheel around the cursor position."""
        if event.xdata is None or event.ydata is None:
            return
        scale = 1.1 if event.button == "up" else 0.9
        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()

        x_left = event.xdata - (event.xdata - xlim[0]) * scale
        x_right = event.xdata + (xlim[1] - event.xdata) * scale
        y_bottom = event.ydata - (event.ydata - ylim[0]) * scale
        y_top = event.ydata + (ylim[1] - event.ydata) * scale

        self._ax.set_xlim(x_left, x_right)
        self._ax.set_ylim(y_bottom, y_top)
        self._canvas.draw()

    def _on_press(self, event) -> None:
        """Start a box-select zoom or reset on double-click."""
        if event.dblclick:
            self._reset_view()
            return
        if event.button == 1 and event.xdata is not None and event.ydata is not None:
            self._drag_start = (event.xdata, event.ydata)

    def _on_motion(self, event) -> None:
        """Draw a selection rectangle while dragging, or show hover tooltip."""
        if self._drag_start is not None:
            # Dragging — draw selection rectangle
            if event.xdata is None or event.ydata is None:
                return
            x0, y0 = self._drag_start
            x1, y1 = event.xdata, event.ydata
            width = x1 - x0
            height = y1 - y0

            if self._drag_rect is not None:
                self._drag_rect.set_width(width)
                self._drag_rect.set_height(height)
            else:
                self._drag_rect = Rectangle(
                    (x0, y0),
                    width,
                    height,
                    linewidth=1,
                    edgecolor="#4FC3F7",
                    facecolor="none",
                    linestyle="--",
                )
                self._ax.add_patch(self._drag_rect)
            self._canvas.draw()
        else:
            # Not dragging — show hover tooltip
            self._show_hover_tooltip(event)

    def _show_hover_tooltip(self, event) -> None:
        """Show a tooltip with wavelength and the nearest curve's intensity."""
        if event.xdata is None or event.ydata is None:
            self._hide_tooltip()
            return

        if not self._curves:
            self._hide_tooltip()
            return

        wl = event.xdata
        mouse_y = event.ydata

        # Find the curve whose value at this wavelength is closest to the
        # cursor's y-position. Only show that curve's intensity.
        best_label = None
        best_val = None
        best_dist = float("inf")

        for label, _color, wavelengths, values in self._curves:
            if wl < wavelengths[0] or wl > wavelengths[-1]:
                continue
            val = float(np.interp(wl, wavelengths, values))
            dist = abs(val - mouse_y)
            if dist < best_dist:
                best_dist = dist
                best_label = label
                best_val = val

        if best_label is None:
            self._hide_tooltip()
            return

        text = f"λ = {wl:.0f} nm\n{best_label}: {best_val:.3f}"

        # Adaptive positioning: if cursor is in the upper half, place tooltip
        # below the cursor; otherwise place it above.
        ylim = self._ax.get_ylim()
        y_mid = (ylim[0] + ylim[1]) / 2.0
        if mouse_y > y_mid:
            offset = (10, -40)
        else:
            offset = (10, 10)

        if self._tooltip_annotation is None:
            self._tooltip_annotation = self._ax.annotate(
                text,
                xy=(wl, mouse_y),
                xytext=offset,
                textcoords="offset points",
                fontsize=8,
                color="#E0E0E0",
                bbox={
                    "boxstyle": "round,pad=0.3",
                    "facecolor": "#333333",
                    "edgecolor": "#666666",
                    "alpha": 0.9,
                },
                zorder=100,
            )
        else:
            self._tooltip_annotation.set_text(text)
            self._tooltip_annotation.xy = (wl, mouse_y)
            self._tooltip_annotation.set_position(offset)

        self._canvas.draw_idle()

    def _hide_tooltip(self, _event=None) -> None:
        """Remove the hover tooltip if visible."""
        if self._tooltip_annotation is not None:
            self._tooltip_annotation.remove()
            self._tooltip_annotation = None
            self._canvas.draw_idle()

    def _on_release(self, event) -> None:
        """Apply the box-select zoom when the mouse is released."""
        if self._drag_start is None or event.xdata is None or event.ydata is None:
            self._drag_start = None
            self._remove_drag_rect()
            return

        x0, y0 = self._drag_start
        x1, y1 = event.xdata, event.ydata
        self._drag_start = None
        self._remove_drag_rect()

        if abs(x1 - x0) < 1e-6 or abs(y1 - y0) < 1e-6:
            return

        x_min, x_max = sorted((x0, x1))
        y_min, y_max = sorted((y0, y1))
        self._ax.set_xlim(x_min, x_max)
        self._ax.set_ylim(y_min, y_max)
        self._canvas.draw()

    def _remove_drag_rect(self) -> None:
        """Remove the temporary selection rectangle."""
        if self._drag_rect is not None:
            self._drag_rect.remove()
            self._drag_rect = None
            self._canvas.draw()

    def _reset_view(self) -> None:
        """Reset the view to the original limits."""
        if self._orig_xlim is not None:
            self._ax.set_xlim(self._orig_xlim)
        if self._orig_ylim is not None:
            self._ax.set_ylim(self._orig_ylim)
        self._canvas.draw()
