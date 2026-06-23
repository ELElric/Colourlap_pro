"""ThicknessOptimizerPage -- Thickness Optimizer page for ColorLab Pro.

Layout (top to bottom):
1. Optimization Target (Dropdown: Max BT2020 Coverage / Max DCI-P3 Coverage / Target White Point / Target Coordinate)
2. RGB Spectrum Selection (R/G/B each with Dropdown + Paste button)
3. Color Filter Selection (RCF/GCF/BCF each with Dropdown + Paste button)
4. Thickness Range Settings (RCF/GCF/BCF min/max range, default 0.1X~5.0X)
5. Start Optimization button
6. Optimization Result Table (columns: Rank / RCF Thickness / GCF Thickness / BCF Thickness / Coverage / Match / White Point)
7. Scan Curve area (Thickness vs Coverage / Thickness vs Coordinate / Thickness vs White Point)

Key implementation:
- Optimization targets map to optimization_controller methods
- Single-channel scan: fix RCF and BCF, sweep GCF from min to max, output three curves
- Scan curves use SpectrumChartWidget (reused as generic line chart)
- Optimization results displayed in QTableWidget
- Uses QThreadPool for background optimization execution
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.widgets.spectrum_chart import SpectrumChartWidget
from colorlab_pro.ui.workers import run_in_background

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPTIMIZATION_TARGETS = [
    "Max BT2020 Coverage",
    "Max DCI-P3 Coverage",
    "Target White Point",
    "Target Coordinate",
]

_STANDARD_GAMUT_MAP = {
    "Max BT2020 Coverage": "BT2020",
    "Max DCI-P3 Coverage": "DCI-P3",
}

_CHANNEL_COLORS = {
    "R": "#FF4444",
    "G": "#44FF44",
    "B": "#4488FF",
}

_SCAN_CURVE_COLORS = {
    "Coverage": "#4FC3F7",
    "Coordinate": "#FF6B6B",
    "White Point": "#4CAF50",
}

# Default thickness range
_THICKNESS_MIN_DEFAULT = 0.0
_THICKNESS_MAX_DEFAULT = 5.0

# Scan resolution
_SCAN_STEPS = 100


# ---------------------------------------------------------------------------
# Helper: Spectrum Selector (Dropdown + Paste button)
# ---------------------------------------------------------------------------


class _SpectrumSelector(QWidget):
    """Spectrum selector component: Dropdown + Paste button."""

    selectionChanged = Signal()  # noqa: N815

    def __init__(self, channel: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel = channel

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Channel label with color
        self._label = QLabel(f"<b>{channel}</b>")
        self._label.setFixedWidth(36)
        color = _CHANNEL_COLORS.get(channel, "#FFFFFF")
        self._label.setStyleSheet(f"color: {color};")
        layout.addWidget(self._label)

        # Dropdown
        self._combo = QComboBox()
        self._combo.setMinimumWidth(120)
        self._combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        layout.addWidget(self._combo, stretch=1)

        # Paste button
        self._paste_btn = QPushButton("Paste")
        self._paste_btn.setFixedWidth(60)
        layout.addWidget(self._paste_btn)

        # Signals
        self._combo.currentIndexChanged.connect(lambda _idx: self.selectionChanged.emit())

    def populate(self, spectra: list[tuple[str, int]]) -> None:
        """Populate the dropdown list.

        Args:
            spectra: [(name, id), ...] list.
        """
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("-- Select --", userData=-1)
        for name, sid in spectra:
            self._combo.addItem(name, userData=sid)
        self._combo.blockSignals(False)

    def current_id(self) -> int:  # noqa: N802
        """Current selected spectrum ID, -1 if none selected."""
        return self._combo.currentData() or -1

    def current_text(self) -> str:  # noqa: N802
        """Current selected text."""
        return self._combo.currentText()

    def set_current_id(self, sid: int) -> None:
        """Set the dropdown selection by spectrum id."""
        for idx in range(self._combo.count()):
            if self._combo.itemData(idx) == sid:
                self._combo.setCurrentIndex(idx)
                return


# ---------------------------------------------------------------------------
# Helper: Thickness Range Control (min/max spinboxes)
# ---------------------------------------------------------------------------


class _ThicknessRangeControl(QWidget):
    """Thickness range control: Min and Max QDoubleSpinBox."""

    rangeChanged = Signal(float)  # noqa: N815

    def __init__(self, channel: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel = channel

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Channel label
        self._label = QLabel(f"<b>{channel}</b>")
        self._label.setFixedWidth(36)
        layout.addWidget(self._label)

        # Min spinbox
        layout.addWidget(QLabel("Min:"))
        self._min_spin = QDoubleSpinBox()
        self._min_spin.setRange(0.0, 20.0)
        self._min_spin.setSingleStep(0.1)
        self._min_spin.setDecimals(2)
        self._min_spin.setValue(_THICKNESS_MIN_DEFAULT)
        self._min_spin.setSuffix("")
        self._min_spin.setMinimumWidth(56)
        layout.addWidget(self._min_spin)

        # Max spinbox
        layout.addWidget(QLabel("Max:"))
        self._max_spin = QDoubleSpinBox()
        self._max_spin.setRange(0.01, 20.0)
        self._max_spin.setSingleStep(0.1)
        self._max_spin.setDecimals(2)
        self._max_spin.setValue(_THICKNESS_MAX_DEFAULT)
        self._max_spin.setSuffix("")
        self._max_spin.setMinimumWidth(56)
        layout.addWidget(self._max_spin)

        layout.addStretch()

        # Signals
        self._min_spin.valueChanged.connect(self.rangeChanged.emit)
        self._max_spin.valueChanged.connect(self.rangeChanged.emit)

    def min_value(self) -> float:
        """Minimum thickness value."""
        return self._min_spin.value()

    def max_value(self) -> float:
        """Maximum thickness value."""
        return self._max_spin.value()


# ---------------------------------------------------------------------------
# Helper: Generic Line Chart (reuses SpectrumChartWidget)
# ---------------------------------------------------------------------------


class _LineChartWidget(SpectrumChartWidget):
    """Generic line chart widget that reuses SpectrumChartWidget infrastructure.

    Overrides axis labels and plot methods for non-spectrum data.
    """

    def __init__(
        self,
        title: str = "",
        xlabel: str = "Thickness (X)",
        ylabel: str = "Value",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chart_title = title
        self._chart_xlabel = xlabel
        self._chart_ylabel = ylabel
        self._reset_axes()

    def _reset_axes(self) -> None:
        """Reset axis labels for generic chart use."""
        self._ax.set_xlabel(self._chart_xlabel)
        self._ax.set_ylabel(self._chart_ylabel)
        self._ax.set_title(self._chart_title)
        self._canvas.draw()

    def plot_line(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        *,
        label: str | None = None,
        color: str | None = None,
        linestyle: str | None = None,
    ) -> None:
        """Plot a generic line.

        Args:
            x_data: X-axis data.
            y_data: Y-axis data.
            label: Optional legend label.
            color: Optional line color.
            linestyle: Optional line style (e.g. '-', '--').
        """
        self._ax.plot(
            x_data,
            y_data,
            label=label or "Data",
            color=color or "#4FC3F7",
            linestyle=linestyle or "-",
        )
        self._ax.legend(facecolor="#1E1E1E", edgecolor="#E0E0E0", labelcolor="#E0E0E0")
        self._store_orig_limits()
        self._canvas.draw()

    def clear(self) -> None:
        """Clear all plotted data and reset axes."""
        self._ax.clear()
        self._ax.set_facecolor("#1E1E1E")
        self._ax.tick_params(colors="#E0E0E0")
        self._ax.xaxis.label.set_color("#E0E0E0")
        self._ax.yaxis.label.set_color("#E0E0E0")
        self._ax.title.set_color("#E0E0E0")
        for spine in self._ax.spines.values():
            spine.set_color("#E0E0E0")
        self._reset_axes()
        self._orig_xlim = None
        self._orig_ylim = None
        self._drag_start = None
        self._drag_rect = None
        self._canvas.draw()


# ---------------------------------------------------------------------------
# Main Page
# ---------------------------------------------------------------------------


class ThicknessOptimizerPage(QWidget):
    """Thickness Optimizer page for ColorLab Pro.

    Provides a complete thickness optimization workflow:
    1. Select optimization target
    2. Select RGB spectra and color filters
    3. Set thickness ranges
    4. Run optimization in background
    5. View results in table and scan curves
    """

    # Emitted when optimization completes with results
    optimization_finished = Signal(list)

    # Emitted with progress text from background thread
    progress_update = Signal(str)

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        optimization_controller: OptimizationController | None = None,
        page_index: int = 3,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_ctrl = spectrum_controller
        self._color_ctrl = color_controller
        self._opt_ctrl = optimization_controller
        self._page_index = page_index

        # Spectrum cache
        self._spectra_cache: dict[int, Spectrum] = {}
        self._spectra_summaries: dict[int, object] = {}

        # Current selected spectrum IDs
        self._rgb_ids: dict[str, int] = {"R": -1, "G": -1, "B": -1}
        self._filter_ids: dict[str, int] = {"RCF": -1, "GCF": -1, "BCF": -1}

        # Cached spectra
        self._original_spectra: dict[str, Spectrum | None] = {
            "R": None,
            "G": None,
            "B": None,
        }
        self._filter_spectra: dict[str, Spectrum | None] = {
            "RCF": None,
            "GCF": None,
            "BCF": None,
        }

        # Optimization results
        self._opt_results: list[dict] = []

        # Target coordinate inputs (for Target White Point / Target Coordinate)
        self._target_xy: XY | None = None

        # Cancellation flag for background optimization
        self._cancelled = False

        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------ #
    # UI Construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        """Build the page layout."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)

        # --- 1. Optimization Target ---
        self._build_optimization_target(outer_layout)

        # --- 2. Spectrum + Thickness Range combined ---
        self._build_spectrum_and_range(outer_layout)

        # --- 3. Start Optimization Button ---
        self._build_start_button(outer_layout)

        # --- 4. Result + Scan Curves (horizontal split) ---
        result_widget = QWidget()
        result_layout = QHBoxLayout(result_widget)
        result_layout.setContentsMargins(0, 0, 0, 0)

        self._build_result_table(result_layout)
        self._build_scan_curves(result_layout)

        outer_layout.addWidget(result_widget, stretch=1)

    def _build_optimization_target(self, parent_layout: QVBoxLayout) -> None:
        """Build the optimization target selector."""
        group = QGroupBox("Optimization Target")
        form = QFormLayout(group)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self._target_combo = QComboBox()
        self._target_combo.addItems(_OPTIMIZATION_TARGETS)
        form.addRow("Target:", self._target_combo)

        # Target coordinate inputs (for Target White Point / Target Coordinate)
        coord_row = QWidget()
        coord_layout = QHBoxLayout(coord_row)
        coord_layout.setContentsMargins(0, 0, 0, 0)
        coord_layout.setSpacing(8)

        coord_layout.addWidget(QLabel("x:"))
        self._target_x_spin = QDoubleSpinBox()
        self._target_x_spin.setRange(0.0, 1.0)
        self._target_x_spin.setSingleStep(0.001)
        self._target_x_spin.setDecimals(4)
        self._target_x_spin.setValue(0.3127)
        self._target_x_spin.setMinimumWidth(80)
        coord_layout.addWidget(self._target_x_spin)

        coord_layout.addWidget(QLabel("y:"))
        self._target_y_spin = QDoubleSpinBox()
        self._target_y_spin.setRange(0.0, 1.0)
        self._target_y_spin.setSingleStep(0.001)
        self._target_y_spin.setDecimals(4)
        self._target_y_spin.setValue(0.3290)
        self._target_y_spin.setMinimumWidth(80)
        coord_layout.addWidget(self._target_y_spin)

        coord_layout.addStretch()

        self._coord_row_widget = coord_row
        form.addRow("Coordinate:", coord_row)

        # Initially hide coordinate row (only shown for Target White Point / Target Coordinate)
        self._coord_row_widget.setVisible(False)

        parent_layout.addWidget(group)

    def _build_spectrum_and_range(self, parent_layout: QVBoxLayout) -> None:
        """Build RGB/CF spectrum selection and thickness range in one combined section."""
        group = QGroupBox("Spectrum & Thickness")
        grid = QGridLayout(group)
        grid.setSpacing(6)

        # Column headers
        grid.addWidget(QLabel("<b>RGB (Emission)</b>"), 0, 0)
        grid.addWidget(QLabel("<b>CF (Transmittance)</b>"), 0, 1)
        grid.addWidget(QLabel("<b>Range (μm)</b>"), 0, 2)

        channels = [
            ("R", "RCF"),
            ("G", "GCF"),
            ("B", "BCF"),
        ]

        for row, (rgb_ch, filter_ch) in enumerate(channels, start=1):
            # RGB selector
            rgb_sel = _SpectrumSelector(rgb_ch)
            setattr(self, f"_rgb_sel_{rgb_ch}", rgb_sel)
            grid.addWidget(rgb_sel, row, 0)

            # CF selector
            filter_sel = _SpectrumSelector(filter_ch)
            setattr(self, f"_filter_sel_{filter_ch}", filter_sel)
            grid.addWidget(filter_sel, row, 1)

            # Thickness range
            range_ctrl = _ThicknessRangeControl(filter_ch)
            setattr(self, f"_range_{filter_ch}", range_ctrl)
            grid.addWidget(range_ctrl, row, 2)

        parent_layout.addWidget(group)

    def _build_start_button(self, parent_layout: QVBoxLayout) -> None:
        """Build the start optimization button."""
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._start_btn = QPushButton("Start Optimization")
        self._start_btn.setFixedHeight(36)
        self._start_btn.setMinimumWidth(200)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setMinimumWidth(80)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._stop_btn)

        btn_row.addStretch()
        parent_layout.addLayout(btn_row)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent_layout.addWidget(self._status_label)

    def _build_result_table(self, parent_layout) -> None:
        """Build the optimization result table."""
        group = QGroupBox("Optimization Result")
        group_layout = QVBoxLayout(group)

        self._result_table = QTableWidget()
        self._result_table.setColumnCount(13)
        self._result_table.setHorizontalHeaderLabels(
            [
                "Rank",
                "RCF (um)",
                "GCF (um)",
                "BCF (um)",
                "Coverage",
                "Match",
                "White Point",
                "R (x, y)",
                "G (x, y)",
                "B (x, y)",
                "R Ratio",
                "G Ratio",
                "B Ratio",
            ]
        )
        self._result_table.setRowCount(0)
        self._result_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._result_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        # Rank/RCF/GCF/BCF/Coverage/Match: ResizeToContents (compact);
        # White Point / RGB xy / Ratios: Stretch to fill remaining space.
        opt_header = self._result_table.horizontalHeader()
        for col in range(6):
            opt_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(6, 13):
            opt_header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        group_layout.addWidget(self._result_table)
        parent_layout.addWidget(group, stretch=1)

    def _build_scan_curves(self, parent_layout) -> None:
        """Build the scan curve area with tabs."""
        group = QGroupBox("Scan Curve")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(4, 8, 4, 4)

        self._scan_tab = QTabWidget()

        # Tab 1: Thickness vs Coverage
        self._chart_coverage = _LineChartWidget(
            title="Thickness vs Coverage",
            xlabel="GCF Thickness (X)",
            ylabel="Coverage (%)",
        )
        self._chart_coverage.setMinimumHeight(200)
        self._scan_tab.addTab(self._chart_coverage, "Thickness vs Coverage")

        # Tab 2: Thickness vs Coordinate
        self._chart_coordinate = _LineChartWidget(
            title="Thickness vs Coordinate",
            xlabel="GCF Thickness (X)",
            ylabel="Delta-xy",
        )
        self._chart_coordinate.setMinimumHeight(200)
        self._scan_tab.addTab(self._chart_coordinate, "Thickness vs Coordinate")

        # Tab 3: Thickness vs White Point
        self._chart_white_point = _LineChartWidget(
            title="Thickness vs White Point",
            xlabel="GCF Thickness (X)",
            ylabel="White Point (x, y)",
        )
        self._chart_white_point.setMinimumHeight(200)
        self._scan_tab.addTab(self._chart_white_point, "Thickness vs White Point")

        group_layout.addWidget(self._scan_tab)
        parent_layout.addWidget(group, stretch=2)

    # ------------------------------------------------------------------ #
    # Signal Wiring
    # ------------------------------------------------------------------ #

    def _wire_signals(self) -> None:
        """Connect all UI signals."""
        # Optimization target changed
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)

        # RGB spectrum selection changed
        for ch in ("R", "G", "B"):
            sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ch}")
            sel.selectionChanged.connect(lambda _ch=ch: self._on_rgb_selection_changed(_ch))

        # Filter selection changed
        for ch in ("RCF", "GCF", "BCF"):
            sel: _SpectrumSelector = getattr(self, f"_filter_sel_{ch}")
            sel.selectionChanged.connect(lambda _ch=ch: self._on_filter_selection_changed(_ch))

        # Start / Stop optimization
        self._start_btn.clicked.connect(self._on_start_optimization)
        self._stop_btn.clicked.connect(self._on_stop_optimization)

        # Progress updates from background thread
        self.progress_update.connect(self._status_label.setText)

        # Paste buttons — pass channel explicitly to avoid underMouse() issues
        for ch in ("R", "G", "B"):
            sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ch}")
            sel._paste_btn.clicked.connect(lambda _checked=False, _ch=ch: self._on_paste(_ch, is_filter=False))
        for ch in ("RCF", "GCF", "BCF"):
            sel: _SpectrumSelector = getattr(self, f"_filter_sel_{ch}")
            sel._paste_btn.clicked.connect(lambda _checked=False, _ch=ch: self._on_paste(_ch, is_filter=True))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def connect_auto_refresh(self, window) -> None:
        """Connect to MainWindow.page_about_to_show for auto-refresh on page switch."""
        window.page_about_to_show.connect(self._on_page_show)

    def refresh_spectrum_list(self) -> None:
        """Refresh all dropdown spectrum lists with channel/category filtering."""
        spectra = self._spectrum_ctrl.list_spectra()
        self._spectra_summaries = {s.id: s for s in spectra}

        # RGB selectors: only show LED/QD category (emission spectra)
        led_spectra = [s for s in spectra if s.category in ("LED", "QD")]
        for ch in ("R", "G", "B"):
            sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ch}")
            filtered = [(s.name, s.id) for s in led_spectra if s.channel == ch]
            sel.populate(filtered)

        # Filter selectors (RCF/GCF/BCF): only show CF category spectra
        cf_spectra = [s for s in spectra if s.category == "CF"]
        for ch in ("RCF", "GCF", "BCF"):
            sel: _SpectrumSelector = getattr(self, f"_filter_sel_{ch}")
            channel_map = {"RCF": "R", "GCF": "G", "BCF": "B"}
            target_ch = channel_map[ch]
            filtered = [(s.name, s.id) for s in cf_spectra if s.channel == target_ch]
            sel.populate(filtered)

    # ------------------------------------------------------------------ #
    # Event Handlers
    # ------------------------------------------------------------------ #

    def _on_page_show(self, page_index: int) -> None:
        """Auto-refresh spectrum list when page is shown."""
        if page_index == self._page_index:
            self.refresh_spectrum_list()

    def _on_target_changed(self, index: int) -> None:
        """Handle optimization target change."""
        target = _OPTIMIZATION_TARGETS[index] if 0 <= index < len(_OPTIMIZATION_TARGETS) else ""
        # Show/hide coordinate input based on target
        self._coord_row_widget.setVisible(target in ("Target White Point", "Target Coordinate"))

    def _on_rgb_selection_changed(self, channel: str) -> None:
        """Handle RGB spectrum selection change."""
        sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{channel}")
        sid = sel.current_id()
        self._rgb_ids[channel] = sid

        if sid >= 0:
            spec = self._spectrum_ctrl.get_spectrum(sid)
            if spec is not None:
                self._spectra_cache[sid] = spec
                self._original_spectra[channel] = spec
            else:
                self._original_spectra[channel] = None
        else:
            self._original_spectra[channel] = None

    def _on_filter_selection_changed(self, channel: str) -> None:
        """Handle color filter selection change, auto-fill thickness from spectrum metadata."""
        sel: _SpectrumSelector = getattr(self, f"_filter_sel_{channel}")
        sid = sel.current_id()
        self._filter_ids[channel] = sid

        if sid >= 0:
            spec = self._spectrum_ctrl.get_spectrum(sid)
            if spec is not None:
                self._spectra_cache[sid] = spec
                self._filter_spectra[channel] = spec
            else:
                self._filter_spectra[channel] = None

            # Auto-fill thickness from spectrum's stored thickness_um
            summary = self._spectra_summaries.get(sid)
            if summary is not None and getattr(summary, "thickness_um", None) is not None:
                ctrl: _ThicknessRangeControl = getattr(self, f"_range_{channel}")
                # Set both min and max to the spectrum's thickness, with a small range around it
                t = summary.thickness_um
                ctrl._min_spin.setValue(max(ctrl._min_spin.minimum(), t * 0.5))
                ctrl._max_spin.setValue(min(ctrl._max_spin.maximum(), t * 2.0))
        else:
            self._filter_spectra[channel] = None

    def _on_paste(self, channel: str, *, is_filter: bool) -> None:
        """Paste spectrum data from clipboard into the specified selector.

        Args:
            channel: Channel identifier (e.g. "R", "G", "B", "RCF", "GCF", "BCF").
            is_filter: True if pasting into a filter selector, False for RGB.
        """
        from PySide6.QtWidgets import QApplication, QMessageBox

        from colorlab_pro.ui.utils.clipboard_parser import parse_spectrum_from_text

        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text.strip():
            return

        try:
            spectrum = parse_spectrum_from_text(text)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Paste Failed", str(exc))
            return

        sid = self._spectrum_ctrl.import_spectrum(spectrum, name="Pasted Spectrum")
        if sid is None:
            return

        self.refresh_spectrum_list()

        # Assign the pasted spectrum to the selector that was clicked.
        if is_filter:
            sel: _SpectrumSelector = getattr(self, f"_filter_sel_{channel}")
            sel.set_current_id(sid)
            self._on_filter_selection_changed(channel)
        else:
            sel = getattr(self, f"_rgb_sel_{channel}")
            sel.set_current_id(sid)
            self._on_rgb_selection_changed(channel)

    def _on_stop_optimization(self) -> None:
        """Request cancellation of the running optimization."""
        self._cancelled = True
        self._status_label.setText("Stopping...")

    def _on_start_optimization(self) -> None:
        """Start the optimization process in background.

        All UI values are read on the main thread and passed as arguments to
        the background function to avoid thread-safety issues with Qt widgets.
        """
        # Validate RGB spectra
        if any(self._original_spectra[ch] is None for ch in ("R", "G", "B")):
            self._status_label.setText("Error: Please select all RGB spectra.")
            return

        # Validate filter spectra
        if any(self._filter_spectra[ch] is None for ch in ("RCF", "GCF", "BCF")):
            self._status_label.setText(
                "Error: Please select all color filter spectra (RCF/GCF/BCF)."
            )
            return

        target_name = self._target_combo.currentText()

        # Read target coordinate if needed (main thread)
        if target_name in ("Target White Point", "Target Coordinate"):
            self._target_xy = XY(
                x=self._target_x_spin.value(),
                y=self._target_y_spin.value(),
            )
        else:
            self._target_xy = None

        # Read all thickness ranges on the main thread (thread-safety fix)
        rcf_min, rcf_max = self._range_RCF.min_value(), self._range_RCF.max_value()
        gcf_min, gcf_max = self._range_GCF.min_value(), self._range_GCF.max_value()
        bcf_min, bcf_max = self._range_BCF.min_value(), self._range_BCF.max_value()

        # Validate min < max
        range_errors: list[str] = []
        if rcf_min >= rcf_max:
            range_errors.append("RCF")
        if gcf_min >= gcf_max:
            range_errors.append("GCF")
        if bcf_min >= bcf_max:
            range_errors.append("BCF")
        if range_errors:
            self._status_label.setText(
                f"Error: Min must be less than Max for: {', '.join(range_errors)}"
            )
            return

        # Snapshot all data needed by the background thread (thread-safety)
        original_spectra = {
            ch: self._original_spectra[ch] for ch in ("R", "G", "B")
        }
        filter_spectra = {
            ch: self._filter_spectra[ch] for ch in ("RCF", "GCF", "BCF")
        }
        target_xy = self._target_xy

        # Reset cancellation flag
        self._cancelled = False

        # Disable start, enable stop
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("Optimizing... Please wait.")

        # Run optimization in background with all data passed as arguments
        run_in_background(
            fn=lambda: self._run_optimization(
                target_name, target_xy, original_spectra, filter_spectra,
                rcf_min, rcf_max, gcf_min, gcf_max, bcf_min, bcf_max,
            ),
            on_result=lambda r: self._on_optimization_complete(r),
            on_error=self._on_optimization_error,
        )

    # ------------------------------------------------------------------ #
    # Optimization Logic
    # ------------------------------------------------------------------ #

    def _run_optimization(
        self,
        target_name: str,
        target_xy: XY | None,
        original_spectra: dict[str, Spectrum | None],
        filter_spectra: dict[str, Spectrum | None],
        rcf_min: float,
        rcf_max: float,
        gcf_min: float,
        gcf_max: float,
        bcf_min: float,
        bcf_max: float,
    ) -> list[dict]:
        """Run the optimization in a background thread.

        All UI values are passed as arguments — this function must NOT access
        any Qt widgets directly (thread safety).

        For coverage targets: sweep GCF, compute coverage/match at each point.
        For white point/coordinate targets: use the display-model L-BFGS-B
        optimizer, then build a scan curve around the optimum.
        """
        std_gamut_name = _STANDARD_GAMUT_MAP.get(target_name)

        if target_name in ("Target White Point", "Target Coordinate") and target_xy is not None:
            return self._run_thickness_optimization(
                target_name, target_xy, original_spectra, filter_spectra,
                rcf_min, rcf_max, gcf_min, gcf_max, bcf_min, bcf_max,
            )
        else:
            return self._run_coverage_scan(
                target_name, std_gamut_name, target_xy,
                original_spectra, filter_spectra,
                rcf_min, rcf_max, gcf_min, gcf_max, bcf_min, bcf_max,
            )

    def _run_thickness_optimization(
        self,
        target_name: str,
        target_xy: XY,
        original_spectra: dict[str, Spectrum | None],
        filter_spectra: dict[str, Spectrum | None],
        rcf_min: float,
        rcf_max: float,
        gcf_min: float,
        gcf_max: float,
        bcf_min: float,
        bcf_max: float,
    ) -> list[dict]:
        """Use the display-model thickness optimizer for white point / coordinate targets.

        Each primary source (R/G/B) passes through its own CF, then the
        filtered spectra are summed — matching the physical display light path.
        After finding the optimum, a local scan around it builds the curves.
        """
        from colorlab_pro.engines.thickness_optimizer import (
            display_transmission_for_thicknesses,
            optimize_thickness_display,
        )

        # Build per-channel source and absorber lists
        sources = [original_spectra[ch] for ch in ("R", "G", "B")]  # type: ignore[list-item]
        filter_list = [filter_spectra[ch] for ch in ("RCF", "GCF", "BCF")]  # type: ignore[list-item]

        # Convert CF transmittance to absorption coefficients.
        # alpha = -log10(T_ref) / d_ref, where d_ref is the reference thickness
        # stored in the CF spectrum's metadata.
        ref_wl = sources[0].wavelengths
        absorbers = []
        for fs in filter_list:
            t_vals = np.interp(ref_wl, fs.wavelengths, fs.values)
            t_vals = np.clip(t_vals, 1e-10, 1.0)
            # Get reference thickness from CF spectrum metadata
            d_ref = 1.0
            if fs.meta:
                d_ref = fs.meta.get("thickness_um", 1.0)
                if d_ref is None or d_ref <= 0:
                    d_ref = 1.0
            alpha_vals = -np.log10(t_vals) / d_ref
            absorbers.append(Spectrum(wavelengths=ref_wl.copy(), values=alpha_vals, unit="1/um"))

        # Per-channel bounds (fixes N-1: each channel uses its own range)
        bounds_um = [
            (rcf_min, rcf_max),
            (gcf_min, gcf_max),
            (bcf_min, bcf_max),
        ]

        # Run L-BFGS-B optimization with the display model.
        # The cancel_callback is invoked after each optimizer iteration; if
        # self._cancelled is True it raises OptimizationCancelled which
        # aborts minimize immediately.
        from colorlab_pro.engines.thickness_optimizer import OptimizationCancelledError

        def _cancel_cb(xk: np.ndarray) -> None:
            if self._cancelled:
                raise OptimizationCancelledError

        try:
            result = optimize_thickness_display(
                target_xy, sources, absorbers, bounds_um=bounds_um,
                cancel_callback=_cancel_cb,
            )
        except OptimizationCancelledError:
            self.progress_update.emit("Optimization cancelled by user.")
            self._cancelled = True
            return []

        rcf_t, gcf_t, bcf_t = result.thicknesses_um

        # Compute per-channel filtered spectra and RGB coordinates
        filtered = display_transmission_for_thicknesses(
            sources, absorbers, (rcf_t, gcf_t, bcf_t)
        )
        r_xy = self._color_ctrl.xy(filtered[0])
        g_xy = self._color_ctrl.xy(filtered[1])
        b_xy = self._color_ctrl.xy(filtered[2])

        r_y = self._color_ctrl.luminance(filtered[0])
        g_y = self._color_ctrl.luminance(filtered[1])
        b_y = self._color_ctrl.luminance(filtered[2])
        total_y = r_y + g_y + b_y
        r_ratio = r_y / total_y if total_y > 0 else 1.0 / 3.0
        g_ratio = g_y / total_y if total_y > 0 else 1.0 / 3.0
        b_ratio = b_y / total_y if total_y > 0 else 1.0 / 3.0

        # The achieved_xy from the engine is the mixed white point (display model)
        achieved_white = result.achieved_xy

        device_gamut = self._color_ctrl.build_gamut_from_primaries_direct(
            name="device",
            red=r_xy,
            green=g_xy,
            blue=b_xy,
            white=achieved_white,
        )

        entry = {
            "rcf": rcf_t,
            "gcf": gcf_t,
            "bcf": bcf_t,
            "coverage": 0.0,
            "match": 0.0,
            "white_xy": achieved_white,
            "coord_delta": result.delta_xy,
            "r_xy": r_xy,
            "g_xy": g_xy,
            "b_xy": b_xy,
            "r_ratio": r_ratio,
            "g_ratio": g_ratio,
            "b_ratio": b_ratio,
        }

        # Compute coverage/match if a gamut target is also applicable
        std_name = _STANDARD_GAMUT_MAP.get(target_name)
        if std_name is not None and device_gamut is not None:
            try:
                entry["coverage"] = self._color_ctrl.coverage(std_name, device_gamut)
                entry["match"] = self._color_ctrl.match(std_name, device_gamut)
            except Exception as exc:  # noqa: BLE001
                from loguru import logger
                logger.warning("Coverage/match computation failed: {}", exc)

        # The L-BFGS-B optimal result is the best solution — insert it
        # at the top of the results list so it appears in the result table.
        results: list[dict] = [entry]
        std_gamut_name = _STANDARD_GAMUT_MAP.get(target_name)
        channel_configs = [
            ("RCF", rcf_t, rcf_min, rcf_max, 0),
            ("GCF", gcf_t, gcf_min, gcf_max, 1),
            ("BCF", bcf_t, bcf_min, bcf_max, 2),
        ]

        scan_coverage: list[list[float]] = [[], [], []]
        scan_coordinate: list[list[float]] = [[], [], []]
        scan_wp_x: list[list[float]] = [[], [], []]
        scan_wp_y: list[list[float]] = [[], [], []]
        scan_values: list[np.ndarray] = []

        for idx, (_ch_name, opt_val, ch_min, ch_max, _) in enumerate(channel_configs):
            ch_span = ch_max - ch_min
            scan_lo = max(ch_min, opt_val - ch_span * 0.25)
            scan_hi = min(ch_max, opt_val + ch_span * 0.25)
            if scan_hi <= scan_lo:
                scan_lo, scan_hi = ch_min, ch_max
            ch_scan = np.linspace(scan_lo, scan_hi, 21)
            scan_values.append(ch_scan)

            for step, val in enumerate(ch_scan):
                if self._cancelled:
                    break
                self.progress_update.emit(f"Scanning RCF/GCF/BCF... ({idx+1}/3, step {step+1}/21)")
                try:
                    thicknesses = [rcf_t, gcf_t, bcf_t]
                    thicknesses[_] = float(val)

                    # Use the same display model as the optimization engine
                    # to ensure wavelength grid consistency
                    filt = display_transmission_for_thicknesses(
                        sources, absorbers, tuple(thicknesses)
                    )

                    r_xy = self._color_ctrl.xy(filt[0])
                    g_xy = self._color_ctrl.xy(filt[1])
                    b_xy = self._color_ctrl.xy(filt[2])

                    r_y = self._color_ctrl.luminance(filt[0])
                    g_y = self._color_ctrl.luminance(filt[1])
                    b_y = self._color_ctrl.luminance(filt[2])
                    weights = [r_y, g_y, b_y]
                    total_w = sum(weights)
                    if total_w > 0 and all(w >= 0 for w in weights):
                        white_xy = self._color_ctrl.mix_xy([r_xy, g_xy, b_xy], weights=weights)
                    else:
                        white_xy = self._color_ctrl.mix_xy([r_xy, g_xy, b_xy])

                    cov = 0.0
                    mat = 0.0
                    if std_gamut_name is not None:
                        device_gamut = self._color_ctrl.build_gamut_from_primaries_direct(
                            name="device", red=r_xy, green=g_xy, blue=b_xy, white=white_xy,
                        )
                        try:
                            cov = self._color_ctrl.coverage(std_gamut_name, device_gamut)
                            mat = self._color_ctrl.match(std_gamut_name, device_gamut)
                        except Exception:  # noqa: BLE001
                            pass

                    coord_delta = float(np.hypot(white_xy.x - target_xy.x, white_xy.y - target_xy.y)) if target_xy is not None else 0.0

                    scan_coverage[idx].append(cov)
                    scan_coordinate[idx].append(coord_delta)
                    scan_wp_x[idx].append(white_xy.x)
                    scan_wp_y[idx].append(white_xy.y)

                    # Collect results for the best sweep (GCF channel for table)
                    if idx == 1:  # GCF sweep for result table
                        use_weights = total_w > 0 and all(w >= 0 for w in weights)
                        results.append({
                            "rcf": rcf_t, "gcf": float(val), "bcf": bcf_t,
                            "coverage": cov, "match": mat,
                            "white_xy": white_xy, "coord_delta": coord_delta,
                            "r_xy": r_xy, "g_xy": g_xy, "b_xy": b_xy,
                            "r_ratio": weights[0] / total_w if use_weights else 1.0 / 3.0,
                            "g_ratio": weights[1] / total_w if use_weights else 1.0 / 3.0,
                            "b_ratio": weights[2] / total_w if use_weights else 1.0 / 3.0,
                        })
                except Exception:  # noqa: BLE001
                    scan_coverage[idx].append(0.0)
                    scan_coordinate[idx].append(float("inf"))
                    scan_wp_x[idx].append(0.0)
                    scan_wp_y[idx].append(0.0)

        if std_gamut_name is not None:
            results.sort(key=lambda r: r["coverage"], reverse=True)
        elif target_xy is not None:
            results.sort(key=lambda r: r["coord_delta"])

        for r in results:
            r["_scan_data"] = {
                "channel_names": ["RCF", "GCF", "BCF"],
                "channel_values": scan_values,
                "coverage": scan_coverage,
                "coordinate": scan_coordinate,
                "wp_x": scan_wp_x,
                "wp_y": scan_wp_y,
            }
        return results

    def _run_coverage_scan(
        self,
        target_name: str,
        std_gamut_name: str | None,
        target_xy: XY | None,
        original_spectra: dict[str, Spectrum | None],
        filter_spectra: dict[str, Spectrum | None],
        rcf_min: float, rcf_max: float,
        gcf_min: float, gcf_max: float,
        bcf_min: float, bcf_max: float,
    ) -> list[dict]:
        """Sweep each channel independently for coverage/match targets."""
        from colorlab_pro.engines.thickness_optimizer import display_transmission_for_thicknesses

        rcf_mid = (rcf_min + rcf_max) / 2.0
        gcf_mid = (gcf_min + gcf_max) / 2.0
        bcf_mid = (bcf_min + bcf_max) / 2.0

        ref_wl = original_spectra["R"].wavelengths
        sources = [original_spectra[ch] for ch in ("R", "G", "B")]
        absorbers = []
        for ch in ("RCF", "GCF", "BCF"):
            fs = filter_spectra[ch]
            t_vals = np.interp(ref_wl, fs.wavelengths, fs.values)
            t_vals = np.clip(t_vals, 1e-10, 1.0)
            d_ref = fs.meta.get("thickness_um", 1.0) if fs.meta else 1.0
            if d_ref is None or d_ref <= 0:
                d_ref = 1.0
            alpha_vals = -np.log10(t_vals) / d_ref
            absorbers.append(Spectrum(wavelengths=ref_wl.copy(), values=alpha_vals, unit="1/um"))

        channel_configs = [
            ("RCF", rcf_min, rcf_max, rcf_mid, gcf_mid, bcf_mid, 0),
            ("GCF", gcf_min, gcf_max, rcf_mid, gcf_mid, bcf_mid, 1),
            ("BCF", bcf_min, bcf_max, rcf_mid, gcf_mid, bcf_mid, 2),
        ]

        results: list[dict] = []
        scan_values: list[np.ndarray] = []
        scan_coverage: list[list[float]] = [[], [], []]
        scan_coordinate: list[list[float]] = [[], [], []]
        scan_wp_x: list[list[float]] = [[], [], []]
        scan_wp_y: list[list[float]] = [[], [], []]

        for idx, (_ch_name, ch_min, ch_max, rcf_v, gcf_v, bcf_v, _) in enumerate(channel_configs):
            ch_scan = np.linspace(ch_min, ch_max, _SCAN_STEPS)
            scan_values.append(ch_scan)

            for step, val in enumerate(ch_scan):
                if self._cancelled:
                    break
                self.progress_update.emit(f"Scanning {_ch_name}... ({idx+1}/3, {step+1}/{_SCAN_STEPS})")
                try:
                    thicknesses = [rcf_v, gcf_v, bcf_v]
                    thicknesses[_] = float(val)
                    filt = display_transmission_for_thicknesses(sources, absorbers, tuple(thicknesses))
                    wp = self._compute_white_xy(filt[0], filt[1], filt[2])

                    r_xy = self._color_ctrl.xy(filt[0])
                    g_xy = self._color_ctrl.xy(filt[1])
                    b_xy = self._color_ctrl.xy(filt[2])

                    cov = 0.0
                    mat = 0.0
                    if std_gamut_name is not None:
                        device_gamut = self._color_ctrl.build_gamut_from_primaries_direct(
                            name="device", red=r_xy, green=g_xy, blue=b_xy, white=wp,
                        )
                        try:
                            cov = self._color_ctrl.coverage(std_gamut_name, device_gamut)
                            mat = self._color_ctrl.match(std_gamut_name, device_gamut)
                        except Exception:  # noqa: BLE001
                            pass

                    coord_delta = float(np.hypot(wp.x - target_xy.x, wp.y - target_xy.y)) if target_xy is not None else 0.0

                    scan_coverage[idx].append(cov)
                    scan_coordinate[idx].append(coord_delta)
                    scan_wp_x[idx].append(wp.x)
                    scan_wp_y[idx].append(wp.y)

                    if idx == 1:  # GCF sweep for result table
                        r_y = self._color_ctrl.luminance(filt[0])
                        g_y = self._color_ctrl.luminance(filt[1])
                        b_y = self._color_ctrl.luminance(filt[2])
                        weights_cv = [r_y, g_y, b_y]
                        total_w = sum(weights_cv)
                        use_weights_cv = total_w > 0 and all(w >= 0 for w in weights_cv)
                        results.append({
                            "rcf": rcf_v, "gcf": float(val), "bcf": bcf_v,
                            "coverage": cov, "match": mat,
                            "white_xy": wp, "coord_delta": coord_delta,
                            "r_xy": r_xy, "g_xy": g_xy, "b_xy": b_xy,
                            "r_ratio": weights_cv[0] / total_w if use_weights_cv else 1.0 / 3.0,
                            "g_ratio": weights_cv[1] / total_w if use_weights_cv else 1.0 / 3.0,
                            "b_ratio": weights_cv[2] / total_w if use_weights_cv else 1.0 / 3.0,
                        })
                except Exception:  # noqa: BLE001
                    scan_coverage[idx].append(0.0)
                    scan_coordinate[idx].append(float("inf"))
                    scan_wp_x[idx].append(0.0)
                    scan_wp_y[idx].append(0.0)

        if std_gamut_name is not None:
            results.sort(key=lambda r: r["coverage"], reverse=True)
        elif target_xy is not None:
            results.sort(key=lambda r: r["coord_delta"])

        for r in results:
            r["_scan_data"] = {
                "channel_names": ["RCF", "GCF", "BCF"],
                "channel_values": scan_values,
                "coverage": scan_coverage,
                "coordinate": scan_coordinate,
                "wp_x": scan_wp_x,
                "wp_y": scan_wp_y,
            }
        return results

    def _compute_white_xy(self, r_spec, g_spec, b_spec):
        """Compute white point xy from three filtered spectra."""
        r_xy = self._color_ctrl.xy(r_spec)
        g_xy = self._color_ctrl.xy(g_spec)
        b_xy = self._color_ctrl.xy(b_spec)
        # Guard against NaN coordinates on all paths
        coords = (r_xy.x, r_xy.y, g_xy.x, g_xy.y, b_xy.x, b_xy.y)
        if any(v != v for v in coords):  # noqa: PLR0124
            return XY(x=1.0 / 3.0, y=1.0 / 3.0)
        r_y = self._color_ctrl.luminance(r_spec)
        g_y = self._color_ctrl.luminance(g_spec)
        b_y = self._color_ctrl.luminance(b_spec)
        weights = [r_y, g_y, b_y]
        total = sum(weights)
        if total > 0 and all(w >= 0 for w in weights):
            return self._color_ctrl.mix_xy([r_xy, g_xy, b_xy], weights=weights)
        return self._color_ctrl.mix_xy([r_xy, g_xy, b_xy], weights=[1.0, 1.0, 1.0])

    def _apply_filter(
        self,
        original: Spectrum,
        filter_spec: Spectrum,
        thickness: float,
    ) -> Spectrum:
        """Apply Beer-Lambert Law: T(lambda) = 10^(-alpha(lambda) * d).

        CF spectra are transmittance (0~1) measured at a reference thickness
        d_ref (stored in filter_spec.meta["thickness_um"]). The absorption
        coefficient is alpha = -log10(T_ref) / d_ref, so the actual
        transmittance at thickness d is T = T_ref ^ (d / d_ref).

        If d_ref is missing, defaults to 1.0 um (legacy behavior).

        Args:
            original: Original spectrum.
            filter_spec: Color filter transmittance spectrum (0~1).
            thickness: Thickness in micrometers.

        Returns:
            Filtered spectrum.
        """
        if filter_spec is None:
            return original

        # Interpolate filter to original wavelength grid
        filter_values = np.interp(
            original.wavelengths,
            filter_spec.wavelengths,
            filter_spec.values,
        )

        # Clamp to (0, 1] to avoid log(0) or negative
        filter_values = np.clip(filter_values, 1e-10, 1.0)

        # Get reference thickness from CF spectrum metadata
        d_ref = 1.0
        if filter_spec.meta:
            d_ref = filter_spec.meta.get("thickness_um", 1.0) or 1.0

        # Correct absorption coefficient: alpha = -log10(T_ref) / d_ref
        alpha = -np.log10(filter_values) / d_ref

        # Beer-Lambert: transmitted = original * 10^(-alpha * d)
        filtered_values = original.values * np.power(10.0, -alpha * thickness)

        return Spectrum(
            wavelengths=original.wavelengths.copy(),
            values=filtered_values,
            unit=original.unit,
            meta={
                **original.meta,
                "filter_applied": True,
                "thickness": thickness,
            },
        )

    # ------------------------------------------------------------------ #
    # Result Display
    # ------------------------------------------------------------------ #

    def _on_optimization_error(self, error: str) -> None:
        """Handle optimization error on the UI thread."""
        from loguru import logger
        logger.debug("_on_optimization_error called: {}", error)
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText(f"Error: {error}")

    def _on_optimization_complete(self, results: list[dict]) -> None:
        """Handle optimization completion on the UI thread."""
        from loguru import logger
        logger.debug("_on_optimization_complete called with {} results", len(results))
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._opt_results = results

        if not results:
            if getattr(self, "_cancelled", False):
                self._status_label.setText("Optimization cancelled by user.")
            else:
                self._status_label.setText("Optimization completed with no results.")
            return

        # Update status
        target_name = self._target_combo.currentText()
        if target_name in ("Max BT2020 Coverage", "Max DCI-P3 Coverage"):
            best = results[0]
            self._status_label.setText(
                f"Optimization complete. Best coverage: {best['coverage']:.2f}% "
                f"(RCF={best['rcf']:.1f}μm, GCF={best['gcf']:.1f}μm, BCF={best['bcf']:.1f}μm)"
            )
        elif target_name in ("Target White Point", "Target Coordinate"):
            best = results[0]
            self._status_label.setText(
                f"Optimization complete. Best delta-xy: {best['coord_delta']:.3f} "
                f"(RCF={best['rcf']:.1f}μm, GCF={best['gcf']:.1f}μm, BCF={best['bcf']:.1f}μm)"
            )

        # Update result table (show top 20)
        self._update_result_table(results[:20])

        # Update scan curves
        if results:
            self._scan_data = results[0].get("_scan_data")
        self._update_scan_curves()

        # Emit signal
        self.optimization_finished.emit(results)

    def _update_result_table(self, results: list[dict]) -> None:
        """Update the optimization result table."""
        self._result_table.setRowCount(len(results))

        for row, res in enumerate(results):
            # Rank
            rank_item = QTableWidgetItem(str(row + 1))
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 0, rank_item)

            # RCF Thickness
            rcf_item = QTableWidgetItem(f"{res['rcf']:.1f}μm")
            rcf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 1, rcf_item)

            # GCF Thickness
            gcf_item = QTableWidgetItem(f"{res['gcf']:.1f}μm")
            gcf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 2, gcf_item)

            # BCF Thickness
            bcf_item = QTableWidgetItem(f"{res['bcf']:.1f}μm")
            bcf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 3, bcf_item)

            # Coverage
            cov_item = QTableWidgetItem(f"{res['coverage']:.2f}")
            cov_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 4, cov_item)

            # Match
            mat_item = QTableWidgetItem(f"{res['match']:.2f}")
            mat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 5, mat_item)

            # White Point
            wp = res["white_xy"]
            wp_item = QTableWidgetItem(f"({wp.x:.3f}, {wp.y:.3f})")
            wp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 6, wp_item)

            # RGB Coordinates
            r_xy = res["r_xy"]
            r_item = QTableWidgetItem(f"({r_xy.x:.3f}, {r_xy.y:.3f})")
            r_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 7, r_item)

            g_xy = res["g_xy"]
            g_item = QTableWidgetItem(f"({g_xy.x:.3f}, {g_xy.y:.3f})")
            g_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 8, g_item)

            b_xy = res["b_xy"]
            b_item = QTableWidgetItem(f"({b_xy.x:.3f}, {b_xy.y:.3f})")
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 9, b_item)

            # RGB Ratios
            r_ratio_item = QTableWidgetItem(f"{res['r_ratio']:.3f}")
            r_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 10, r_ratio_item)

            g_ratio_item = QTableWidgetItem(f"{res['g_ratio']:.3f}")
            g_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 11, g_ratio_item)

            b_ratio_item = QTableWidgetItem(f"{res['b_ratio']:.3f}")
            b_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._result_table.setItem(row, 12, b_ratio_item)

    def _update_scan_curves(self) -> None:
        """Update the scan curve charts with all three channel curves."""
        if not hasattr(self, "_scan_data"):
            return

        data = self._scan_data
        channel_names = data["channel_names"]
        channel_values = data["channel_values"]
        channel_colors = {"RCF": "#FF4444", "GCF": "#44FF44", "BCF": "#4488FF"}

        # --- Thickness vs Coverage ---
        self._chart_coverage.clear()
        for idx, ch in enumerate(channel_names):
            n = len(data["coverage"][idx])
            self._chart_coverage.plot_line(
                channel_values[idx][:n],
                np.array(data["coverage"][idx]),
                label=ch,
                color=channel_colors.get(ch, "#FFFFFF"),
            )

        # --- Thickness vs Coordinate ---
        self._chart_coordinate.clear()
        for idx, ch in enumerate(channel_names):
            n = len(data["coordinate"][idx])
            coord_data = np.array(data["coordinate"][idx])
            coord_data[coord_data == float("inf")] = np.nan
            self._chart_coordinate.plot_line(
                channel_values[idx][:n],
                coord_data,
                label=ch,
                color=channel_colors.get(ch, "#FFFFFF"),
            )

        # --- Thickness vs White Point ---
        self._chart_white_point.clear()
        for idx, ch in enumerate(channel_names):
            n = len(data["wp_x"][idx])
            self._chart_white_point.plot_line(
                channel_values[idx][:n],
                np.array(data["wp_x"][idx]),
                label=f"{ch} x",
                color=channel_colors.get(ch, "#FFFFFF"),
            )
            self._chart_white_point.plot_line(
                channel_values[idx][:n],
                np.array(data["wp_y"][idx]),
                label=f"{ch} y",
                color=channel_colors.get(ch, "#FFFFFF"),
                linestyle="--",
            )
