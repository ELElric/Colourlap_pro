"""GamutCalculatorPage -- 核心色域计算页面.

新布局特性：
- 控制面板一栏三列（Spectrum / Color Filter / Thickness）
- CIE 1931 / RGBW 数据表 / CIE 1976 一栏三列
- Spectrum Preview 三栏并排，位于 CIE 图下方
- Gamut Result 表格独占结果区
- 水平方向 QSplitter 可调；垂直方向固定比例
- 布局状态通过 QSettings 自动保存/恢复
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.widgets.cie_diagram import CIECanvas
from colorlab_pro.ui.widgets.spectrum_chart import SpectrumChartWidget

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_THICKNESS_MIN = 0.0
_THICKNESS_MAX = 5.0
_THICKNESS_STEP = 0.01
_THICKNESS_DEFAULT = 1.0

_STANDARD_GAMUTS = ["sRGB", "NTSC", "DCI-P3", "BT2020"]

_CHANNEL_COLORS = {
    "R": "#FF4444",
    "G": "#44FF44",
    "B": "#4488FF",
}

# QSettings key for splitter state
_SETTINGS_ORG = "ColorLabPro"
_SETTINGS_APP = "ColorLabPro"
_SETTINGS_KEY = "gamut_calculator_layout_v2"


# ---------------------------------------------------------------------------
# 辅助：光谱选择行（Dropdown + Paste 按钮）
# ---------------------------------------------------------------------------


class _SpectrumSelector(QWidget):
    """光谱选择组件：Dropdown + Paste 按钮."""

    selectionChanged = Signal()  # noqa: N815

    def __init__(self, channel: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel = channel

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 通道标签
        self._label = QLabel(f"<b>{channel}</b>")
        self._label.setFixedWidth(24)
        color = _CHANNEL_COLORS.get(channel, "#FFFFFF")
        self._label.setStyleSheet(f"color: {color};")
        layout.addWidget(self._label)

        # Dropdown
        self._combo = QComboBox()
        self._combo.setMinimumWidth(60)
        self._combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        layout.addWidget(self._combo, stretch=1)

        # Paste 按钮（保持固定宽度，不随 splitter 拉伸）
        self._paste_btn = QPushButton("Paste")
        paste_fm = self._paste_btn.fontMetrics()
        paste_width = paste_fm.horizontalAdvance("Paste") + 20
        self._paste_btn.setFixedWidth(paste_width)
        self._paste_btn.setToolTip("Paste spectrum from clipboard")
        self._paste_btn.setStyleSheet("QPushButton { padding-left: 2px; padding-right: 2px; }")
        layout.addWidget(self._paste_btn)

        self.setMinimumWidth(160)

        # 信号：QComboBox currentIndexChanged 会携带 index 参数，
        # 但 selectionChanged 是无参信号，因此用 lambda 转发。
        self._combo.currentIndexChanged.connect(lambda _idx: self.selectionChanged.emit())

    def populate(self, spectra: list[tuple[str, int]]) -> None:
        """填充下拉列表."""
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("-- Select --", userData=-1)
        for name, sid in spectra:
            self._combo.addItem(name, userData=sid)
        self._combo.blockSignals(False)

    def current_id(self) -> int:  # noqa: N802
        """当前选中的光谱 ID，-1 表示未选中."""
        data = self._combo.currentData()
        return data if data is not None else -1

    def current_text(self) -> str:  # noqa: N802
        """当前选中的文本."""
        return self._combo.currentText()

    def set_current_id(self, sid: int) -> None:
        """Set the dropdown selection by spectrum id."""
        for idx in range(self._combo.count()):
            if self._combo.itemData(idx) == sid:
                self._combo.setCurrentIndex(idx)
                return


# ---------------------------------------------------------------------------
# 辅助：厚度控制（[-] [SpinBox] [+] + Step）
# ---------------------------------------------------------------------------


class _ThicknessControl(QWidget):
    """厚度控制组件：[-] [数值] [+] + Step 设置."""

    valueChanged = Signal(float)  # noqa: N815

    def __init__(self, channel: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel = channel

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._minus_btn = QPushButton("-")
        btn_fm = self._minus_btn.fontMetrics()
        self._step_btn_width = max(40, btn_fm.horizontalAdvance("+") + 20)
        self._minus_btn.setMinimumWidth(self._step_btn_width)
        self._minus_btn.setStyleSheet("QPushButton { padding-left: 2px; padding-right: 2px; }")
        layout.addWidget(self._minus_btn)

        self._spinbox = QDoubleSpinBox()
        self._spinbox.setRange(_THICKNESS_MIN, _THICKNESS_MAX)
        self._spinbox.setSingleStep(_THICKNESS_STEP)
        self._spinbox.setDecimals(2)
        self._spinbox.setValue(_THICKNESS_DEFAULT)
        self._spinbox.setSuffix("")
        self._spinbox.setMinimumWidth(80)
        layout.addWidget(self._spinbox)

        self._plus_btn = QPushButton("+")
        self._plus_btn.setMinimumWidth(self._step_btn_width)
        self._plus_btn.setStyleSheet("QPushButton { padding-left: 2px; padding-right: 2px; }")
        layout.addWidget(self._plus_btn)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Step:"))
        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.01, 1.0)
        self._step_spin.setSingleStep(0.01)
        self._step_spin.setDecimals(2)
        self._step_spin.setValue(_THICKNESS_STEP)
        self._step_spin.setSuffix("")
        self._step_spin.setMinimumWidth(70)
        layout.addWidget(self._step_spin)

        self.setMinimumWidth(260)
        layout.addStretch()

        self._minus_btn.clicked.connect(self._on_minus)
        self._plus_btn.clicked.connect(self._on_plus)
        self._spinbox.valueChanged.connect(self._on_value_changed)
        self._step_spin.valueChanged.connect(self._on_step_changed)

    def value(self) -> float:
        return self._spinbox.value()

    def set_value(self, val: float) -> None:  # noqa: N802
        self._spinbox.setValue(val)

    def block_signals(self, block: bool) -> None:
        """Block or unblock spinbox signals (public API)."""
        self._spinbox.blockSignals(block)

    def _on_step_changed(self) -> None:
        self._spinbox.setSingleStep(self._step_spin.value())

    def _on_minus(self) -> None:
        step = self._step_spin.value()
        new_val = max(self._spinbox.minimum(), self._spinbox.value() - step)
        new_val = round(new_val / step) * step
        new_val = max(self._spinbox.minimum(), new_val)
        self._spinbox.setValue(new_val)

    def _on_plus(self) -> None:
        step = self._step_spin.value()
        new_val = min(self._spinbox.maximum(), self._spinbox.value() + step)
        new_val = round(new_val / step) * step
        new_val = min(self._spinbox.maximum(), new_val)
        self._spinbox.setValue(new_val)

    def _on_value_changed(self, val: float) -> None:
        self.valueChanged.emit(val)


# ---------------------------------------------------------------------------
# 主页面
# ---------------------------------------------------------------------------


class GamutCalculatorPage(QWidget):
    """Gamut Calculator 核心页面，支持可拖动布局与状态保存."""

    white_point_calculated = Signal(object, object, object)

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        page_index: int = 5,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_ctrl = spectrum_controller
        self._color_ctrl = color_controller
        self._page_index = page_index

        self._spectra_cache: dict[int, Spectrum] = {}
        self._spectra_summaries: dict[int, object] = {}

        self._mode: str = "rgb"
        self._rgb_ids: dict[str, int] = {"R": -1, "G": -1, "B": -1}
        self._filter_ids: dict[str, int] = {"RCF": -1, "GCF": -1, "BCF": -1}
        self._white_id: int = -1
        self._white_spectrum: Spectrum | None = None

        self._thickness: dict[str, float] = {
            "RCF": _THICKNESS_DEFAULT,
            "GCF": _THICKNESS_DEFAULT,
            "BCF": _THICKNESS_DEFAULT,
        }

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
        self._filtered_spectra: dict[str, Spectrum | None] = {
            "R": None,
            "G": None,
            "B": None,
        }

        self._splitters: list[QSplitter] = []
        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)

        # Deferred auto-select state to keep sidebar switching responsive.
        self._pending_auto_select = False
        self._deferred_spectra: list | None = None

        self._build_ui()
        self._wire_signals()
        self._update_visibility()
        self._restore_layout()

    # ------------------------------------------------------------------ #
    # UI 构建
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        """构建页面布局：两行，每行两列.

        Stretch ratios: Mode(1) : Input(5) : Charts(12) : Data(5) = 23 parts total.
        """
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)

        # --- 0. Mode Selection + Display Options（固定小高度） ---
        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["RGB + Color Filter", "White + Color Filter"])
        mode_layout.addWidget(self._mode_combo)
        mode_layout.addSpacing(16)

        self._show_original_cb = QCheckBox("Show Original")
        self._show_original_cb.setChecked(True)
        self._show_filtered_cb = QCheckBox("Show Filtered")
        self._show_filtered_cb.setChecked(True)
        self._show_white_cb = QCheckBox("Show White Point")
        self._show_white_cb.setChecked(True)
        self._show_trajectory_cb = QCheckBox("Show Trajectory")
        self._show_trajectory_cb.setChecked(True)
        self._show_triangle_cb = QCheckBox("Show Triangle")
        self._show_triangle_cb.setChecked(True)
        mode_layout.addWidget(self._show_original_cb)
        mode_layout.addWidget(self._show_filtered_cb)
        mode_layout.addWidget(self._show_white_cb)
        mode_layout.addWidget(self._show_trajectory_cb)
        mode_layout.addWidget(self._show_triangle_cb)
        mode_layout.addSpacing(16)

        self._ref_gamut_cbs: dict[str, QCheckBox] = {}
        for name in ("sRGB", "NTSC", "DCI-P3", "BT2020"):
            cb = QCheckBox(name)
            cb.setChecked(name != "sRGB")
            self._ref_gamut_cbs[name] = cb
            mode_layout.addWidget(cb)
        mode_layout.addStretch()
        outer_layout.addWidget(mode_widget, stretch=1)

        # --- 1. Input Parameters ---
        outer_layout.addWidget(self._build_control_panels(), stretch=5)

        # --- 2. 中间行：CIE 图 | 光谱图 | 色域结果（三等分） ---
        from PySide6.QtWidgets import QGridLayout

        row1_widget = QWidget()
        row1_grid = QGridLayout(row1_widget)
        row1_grid.setContentsMargins(0, 0, 0, 0)
        row1_grid.setSpacing(6)
        row1_grid.setColumnStretch(0, 1)
        row1_grid.setColumnStretch(1, 1)
        row1_grid.setColumnStretch(2, 1)

        cie_widget = self._build_cie_diagrams()
        spectrum_widget = self._build_spectrum_preview()
        result_widget = self._build_results()

        row1_grid.addWidget(cie_widget, 0, 0)
        row1_grid.addWidget(spectrum_widget, 0, 1)
        row1_grid.addWidget(result_widget, 0, 2)
        outer_layout.addWidget(row1_widget, stretch=12)

        # --- 3. 底部行：色坐标数据（全宽） ---
        outer_layout.addWidget(self._build_chromaticity_data(), stretch=5)

    def _build_control_panels(self) -> QWidget:
        """构建紧凑的输入参数面板：一栏三列.

        把 Spectrum Selection / Color Filter Selection / Thickness Controls
        合并到一个 GroupBox 内，减少标题和边距占用的垂直空间。
        """
        group = QGroupBox("Input Parameters")
        outer_layout = QVBoxLayout(group)
        outer_layout.setContentsMargins(6, 8, 6, 6)
        outer_layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setOpaqueResize(False)
        self._splitters.append(splitter)

        # Column 1: Spectrum Selection
        spectrum_panel = QWidget()
        spectrum_layout = QVBoxLayout(spectrum_panel)
        spectrum_layout.setContentsMargins(0, 0, 0, 0)
        spectrum_layout.setSpacing(6)
        spectrum_layout.addWidget(QLabel("<b>Spectrum</b>"))

        self._rgb_group_widget = QWidget()
        rgb_layout = QVBoxLayout(self._rgb_group_widget)
        rgb_layout.setContentsMargins(0, 0, 0, 0)
        rgb_layout.setSpacing(6)
        for ch in ("R", "G", "B"):
            selector = _SpectrumSelector(ch)
            rgb_layout.addWidget(selector)
            setattr(self, f"_rgb_sel_{ch}", selector)
        spectrum_layout.addWidget(self._rgb_group_widget)

        self._white_group_widget = QWidget()
        white_layout = QVBoxLayout(self._white_group_widget)
        white_layout.setContentsMargins(0, 0, 0, 0)
        white_layout.setSpacing(6)
        self._white_sel = _SpectrumSelector("W")
        white_layout.addWidget(self._white_sel)
        spectrum_layout.addWidget(self._white_group_widget)
        self._white_group_widget.setVisible(False)

        spectrum_layout.addStretch()
        spectrum_panel.setMinimumWidth(180)
        splitter.addWidget(spectrum_panel)

        # Column 2: Color Filter Selection
        filter_panel = QWidget()
        filter_layout = QVBoxLayout(filter_panel)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)
        filter_layout.addWidget(QLabel("<b>Color Filter</b>"))
        for ch in ("RCF", "GCF", "BCF"):
            selector = _SpectrumSelector(ch)
            filter_layout.addWidget(selector)
            setattr(self, f"_filter_sel_{ch}", selector)
        filter_layout.addStretch()
        filter_panel.setMinimumWidth(180)
        splitter.addWidget(filter_panel)

        # Column 3: Thickness Controls
        thickness_panel = QWidget()
        thickness_layout = QVBoxLayout(thickness_panel)
        thickness_layout.setContentsMargins(0, 0, 0, 0)
        thickness_layout.setSpacing(6)
        thickness_layout.addWidget(QLabel("<b>Thickness (μm)</b>"))
        for ch in ("RCF", "GCF", "BCF"):
            ctrl_layout = QHBoxLayout()
            ctrl_layout.setContentsMargins(0, 0, 0, 0)
            ctrl_layout.setSpacing(4)
            ctrl = _ThicknessControl(ch)
            ctrl_layout.addWidget(ctrl)
            thickness_layout.addLayout(ctrl_layout)
            setattr(self, f"_thickness_{ch}", ctrl)

        thickness_layout.addStretch()

        thickness_panel.setMinimumWidth(280)
        splitter.addWidget(thickness_panel)

        # 默认宽度比例：2 : 2 : 3
        splitter.setSizes([180, 180, 260])
        outer_layout.addWidget(splitter)
        return group

    def _build_cie_diagrams(self) -> QWidget:
        """构建 CIE 区域：CIE 1931 + CIE 1976，使用 Tab 切换."""
        group = QGroupBox("CIE Chromaticity Diagrams")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(6, 8, 6, 6)

        # Tab widget: CIE 1931 xy | CIE 1976 u'v'
        self._cie_tab_widget = QTabWidget()

        # Tab 1: CIE 1931 xy
        self._cie_xy_canvas = CIECanvas(mode="xy")
        self._cie_xy_canvas.set_reference_gamuts(["NTSC", "DCI-P3", "BT2020"])
        self._cie_xy_canvas.setMinimumHeight(200)
        self._cie_tab_widget.addTab(self._cie_xy_canvas, "CIE 1931 xy")

        # Tab 2: CIE 1976 u'v'
        self._cie_uv_canvas = CIECanvas(mode="uv")
        self._cie_uv_canvas.set_reference_gamuts(["NTSC", "DCI-P3", "BT2020"])
        self._cie_uv_canvas.setMinimumHeight(200)
        self._cie_tab_widget.addTab(self._cie_uv_canvas, "CIE 1976 u'v'")

        group_layout.addWidget(self._cie_tab_widget)

        wrapper = QWidget()
        wrapper.setLayout(group_layout)
        return wrapper

    def _build_spectrum_preview(self) -> QWidget:
        """构建光谱预览区域，使用 Tab 切换不同视图."""
        group = QGroupBox("Spectrum Preview")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(6, 8, 6, 6)

        # Tab widget: Filtered | Original | Compare
        self._spectrum_tab_widget = QTabWidget()

        # Tab 1: Filtered Spectrum
        self._filtered_chart = SpectrumChartWidget()
        self._filtered_chart.setMinimumHeight(200)
        self._filtered_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._spectrum_tab_widget.addTab(self._filtered_chart, "Filtered Spectrum")

        # Tab 2: Original Spectrum
        self._original_chart = SpectrumChartWidget()
        self._original_chart.setMinimumHeight(200)
        self._original_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._spectrum_tab_widget.addTab(self._original_chart, "Original Spectrum")

        # Tab 3: Compare Mode
        compare_widget = QWidget()
        compare_layout = QVBoxLayout(compare_widget)
        compare_layout.setContentsMargins(0, 0, 0, 0)
        compare_layout.setSpacing(4)

        # Checkbox row to toggle individual curves
        compare_cb_row = QHBoxLayout()
        compare_cb_row.setContentsMargins(0, 0, 0, 0)
        compare_cb_row.setSpacing(6)
        self._compare_cbs: dict[str, QCheckBox] = {}
        self._compare_cb_colors: dict[str, str] = {}
        self._compare_cb_defaults: dict[str, str] = {}
        for key, label, color in [
            ("RCF", "RCF", "#FF8888"),
            ("GCF", "GCF", "#88FF88"),
            ("BCF", "BCF", "#88AAFF"),
            ("R", "LED R", "#FF4444"),
            ("G", "LED G", "#44FF44"),
            ("B", "LED B", "#4488FF"),
        ]:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setStyleSheet(f"QCheckBox {{ color: {color}; spacing: 4px; }}")
            cb.stateChanged.connect(self._on_compare_cb_changed)
            compare_cb_row.addWidget(cb)
            self._compare_cbs[key] = cb
            self._compare_cb_colors[key] = color
            self._compare_cb_defaults[key] = label
        compare_cb_row.addStretch()
        compare_cb_widget = QWidget()
        compare_cb_widget.setLayout(compare_cb_row)
        compare_layout.addWidget(compare_cb_widget)

        self._compare_chart = SpectrumChartWidget()
        self._compare_chart.setMinimumHeight(160)
        self._compare_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        compare_layout.addWidget(self._compare_chart)
        self._spectrum_tab_widget.addTab(compare_widget, "Compare Mode")

        group_layout.addWidget(self._spectrum_tab_widget)

        wrapper = QWidget()
        wrapper.setLayout(group_layout)
        return wrapper

    def _build_chromaticity_data(self) -> QGroupBox:
        """构建底部数据区：左列 RGBW 色坐标，右列 RGB 光谱参数."""
        from PySide6.QtWidgets import QGridLayout

        group = QGroupBox("Data")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(4, 8, 4, 4)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("<b>RGBW Chromaticity Data</b>"), 0, 0)
        grid.addWidget(QLabel("<b>RGB Spectrum Data</b>"), 0, 1)

        self._chromaticity_table = self._create_chromaticity_table()
        grid.addWidget(self._chromaticity_table, 1, 0)

        self._spectrum_data_table = self._create_spectrum_data_table()
        grid.addWidget(self._spectrum_data_table, 1, 1)

        group_layout.addLayout(grid)
        return group

    @staticmethod
    def _create_chromaticity_table() -> QTableWidget:
        """创建 RGBW 色坐标数据表."""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            ["Channel", "x", "y", "u'", "v'", "X", "Y", "CCT"]
        )
        table.setRowCount(4)
        for row, name in enumerate(("R", "G", "B", "White")):
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 0, item)
            for col in range(1, 8):
                dash = QTableWidgetItem("--")
                dash.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                dash.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setItem(row, col, dash)

        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        for col in range(8):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        return table

    @staticmethod
    def _create_spectrum_data_table() -> QTableWidget:
        """创建 RGB 光谱参数表（Peak / FWHM / Dominant λ / Purity）."""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["Channel", "Peak (nm)", "FWHM (nm)", "Dom. \u03bb (nm)", "Purity"]
        )
        table.setRowCount(3)
        for row, name in enumerate(("R", "G", "B")):
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 0, item)
            for col in range(1, 5):
                dash = QTableWidgetItem("--")
                dash.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                dash.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setItem(row, col, dash)

        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        for col in range(5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        return table

    def _build_results(self) -> QGroupBox:
        """构建结果区域：CIE 1931 和 CIE 1976 两个表格上下排列."""
        gamut_group = QGroupBox("Gamut Result")
        gamut_layout = QVBoxLayout(gamut_group)
        gamut_layout.setContentsMargins(8, 10, 8, 8)
        gamut_layout.setSpacing(8)

        gamut_layout.addWidget(QLabel("<b>CIE 1931 xy</b>"))
        self._gamut_table_1931 = self._create_gamut_table()
        gamut_layout.addWidget(self._gamut_table_1931)

        gamut_layout.addWidget(QLabel("<b>CIE 1976 u'v'</b>"))
        self._gamut_table_1976 = self._create_gamut_table()
        gamut_layout.addWidget(self._gamut_table_1976)

        return gamut_group

    @staticmethod
    def _create_gamut_table() -> QTableWidget:
        """创建单个色域结果表格."""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Standard", "Coverage (%)", "Match (%)"])
        table.setRowCount(len(_STANDARD_GAMUTS))
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        for i, name in enumerate(_STANDARD_GAMUTS):
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 0, item)
            for col in (1, 2):
                dash_item = QTableWidgetItem("--")
                dash_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(i, col, dash_item)

        header = table.horizontalHeader()
        for col in range(3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        return table

    # ------------------------------------------------------------------ #
    # 布局保存/恢复
    # ------------------------------------------------------------------ #

    def _save_layout(self) -> None:
        """保存所有 splitter 状态到 QSettings."""
        states = {}
        for i, splitter in enumerate(self._splitters):
            states[str(i)] = splitter.saveState().toBase64().data().decode("ascii")
        self._settings.setValue(_SETTINGS_KEY, states)

    def _restore_layout(self) -> None:
        """从 QSettings 恢复 splitter 状态."""
        value = self._settings.value(_SETTINGS_KEY)
        # QSettings may return dict-like objects that don't pass isinstance(dict)
        if value is None:
            return
        try:
            states = dict(value) if not isinstance(value, dict) else value
        except (TypeError, ValueError):
            return
        for i, splitter in enumerate(self._splitters):
            state_b64 = states.get(str(i))
            if state_b64:
                from PySide6.QtCore import QByteArray

                splitter.restoreState(QByteArray.fromBase64(state_b64.encode("ascii")))

    # ------------------------------------------------------------------ #
    # 信号连接
    # ------------------------------------------------------------------ #

    def _wire_signals(self) -> None:
        """连接所有 UI 信号."""
        # Mode switch
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # RGB 光谱选择变化
        for ch in ("R", "G", "B"):
            sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ch}")
            sel.selectionChanged.connect(lambda _ch=ch: self._on_rgb_selection_changed(_ch))

        # White spectrum selection change
        self._white_sel.selectionChanged.connect(self._on_white_selection_changed)

        # 彩膜选择变化
        for ch in ("RCF", "GCF", "BCF"):
            sel: _SpectrumSelector = getattr(self, f"_filter_sel_{ch}")
            sel.selectionChanged.connect(lambda _ch=ch: self._on_filter_selection_changed(_ch))

        # 厚度变化 -> 实时更新
        for ch in ("RCF", "GCF", "BCF"):
            ctrl: _ThicknessControl = getattr(self, f"_thickness_{ch}")
            ctrl.valueChanged.connect(lambda val, _ch=ch: self._on_thickness_changed(_ch, val))

        # CIE 图工具栏（同时同步两个 canvas）
        self._show_original_cb.stateChanged.connect(self._on_show_options_changed)
        self._show_filtered_cb.stateChanged.connect(self._on_show_options_changed)
        self._show_white_cb.stateChanged.connect(self._on_show_options_changed)
        self._show_trajectory_cb.stateChanged.connect(self._on_show_options_changed)
        self._show_triangle_cb.stateChanged.connect(self._on_show_options_changed)
        for _name, cb in self._ref_gamut_cbs.items():
            cb.stateChanged.connect(self._on_reference_gamuts_changed)

        # Paste 按钮
        for ch in ("R", "G", "B"):
            sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ch}")
            sel._paste_btn.clicked.connect(lambda: self._on_paste())
        self._white_sel._paste_btn.clicked.connect(lambda: self._on_paste())
        for ch in ("RCF", "GCF", "BCF"):
            sel: _SpectrumSelector = getattr(self, f"_filter_sel_{ch}")
            sel._paste_btn.clicked.connect(lambda: self._on_paste())

        # Splitter 状态变化时保存布局
        for splitter in self._splitters:
            splitter.splitterMoved.connect(self._save_layout)

    def _on_show_options_changed(self) -> None:
        """同步两个 canvas 的显示选项."""
        show_original = self._show_original_cb.isChecked()
        show_filtered = self._show_filtered_cb.isChecked()
        show_white = self._show_white_cb.isChecked()
        show_trajectory = self._show_trajectory_cb.isChecked()
        show_triangle = self._show_triangle_cb.isChecked()
        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.set_show_original(show_original)
            canvas.set_show_filtered(show_filtered)
            canvas.set_show_white_point(show_white)
            canvas.set_show_trajectory(show_trajectory)
            canvas.set_show_triangle(show_triangle)
            canvas.refresh()

    def _on_compare_cb_changed(self) -> None:
        """Rebuild the Compare Mode chart based on checkbox selection."""
        self._update_compare_chart()

    def _update_compare_checkbox_labels(self) -> None:
        """Update checkbox labels to show the selected material names."""
        # CF checkboxes: RCF/GCF/BCF
        for ch in ("RCF", "GCF", "BCF"):
            cb = self._compare_cbs.get(ch)
            if cb is None:
                continue
            sid = self._filter_ids.get(ch, -1)
            summary = self._spectra_summaries.get(sid) if sid >= 0 else None
            name = getattr(summary, "name", None) if summary is not None else None
            default = self._compare_cb_defaults.get(ch, ch)
            cb.setText(name if name else default)

        # LED checkboxes: R/G/B
        if self._mode == "white":
            # In white mode, R checkbox represents the white spectrum
            cb = self._compare_cbs.get("R")
            if cb is not None:
                sid = self._white_id
                summary = self._spectra_summaries.get(sid) if sid >= 0 else None
                name = getattr(summary, "name", None) if summary is not None else None
                default = self._compare_cb_defaults.get("R", "LED R")
                cb.setText(name if name else default)
            # G and B have no spectrum in white mode, reset to defaults
            for ch in ("G", "B"):
                cb = self._compare_cbs.get(ch)
                if cb is not None:
                    cb.setText(self._compare_cb_defaults.get(ch, f"LED {ch}"))
        else:
            for ch in ("R", "G", "B"):
                cb = self._compare_cbs.get(ch)
                if cb is None:
                    continue
                sid = self._rgb_ids.get(ch, -1)
                summary = self._spectra_summaries.get(sid) if sid >= 0 else None
                name = getattr(summary, "name", None) if summary is not None else None
                default = self._compare_cb_defaults.get(ch, f"LED {ch}")
                cb.setText(name if name else default)

    def _update_compare_chart(self) -> None:
        """Update only the Compare Mode chart (used by checkbox callbacks)."""
        self._compare_chart.clear()
        compare_items: list[tuple] = []
        cf_colors = {"RCF": "#FF8888", "GCF": "#88FF88", "BCF": "#88AAFF"}
        for ch in ("RCF", "GCF", "BCF"):
            if not self._compare_cbs.get(ch) or not self._compare_cbs[ch].isChecked():
                continue
            cf_spec = self._filter_spectra.get(ch)
            if cf_spec is not None:
                # Use the actual spectrum name from the material library
                sid = self._filter_ids.get(ch, -1)
                summary = self._spectra_summaries.get(sid)
                label = summary.name if summary is not None else f"CF {ch}"
                compare_items.append((cf_spec, label, cf_colors.get(ch, "#FFFFFF")))
        if self._mode == "white" and self._white_spectrum is not None:
            if self._compare_cbs.get("R") and self._compare_cbs["R"].isChecked():
                sid = self._white_id
                summary = self._spectra_summaries.get(sid)
                label = summary.name if summary is not None else "White"
                compare_items.append((self._white_spectrum, label, "#FFFFFF"))
        else:
            for ch in ("R", "G", "B"):
                if not self._compare_cbs.get(ch) or not self._compare_cbs[ch].isChecked():
                    continue
                orig = self._original_spectra.get(ch)
                if orig is not None:
                    sid = self._rgb_ids.get(ch, -1)
                    summary = self._spectra_summaries.get(sid)
                    label = summary.name if summary is not None else f"LED {ch}"
                    compare_items.append((orig, label, _CHANNEL_COLORS[ch]))
        if compare_items:
            self._compare_chart.plot_spectra(compare_items)

    # ------------------------------------------------------------------ #
    # 公共 API
    # ------------------------------------------------------------------ #

    def connect_auto_refresh(self, window) -> None:
        """连接到 MainWindow.page_about_to_show 实现页面切换时自动刷新."""
        window.page_about_to_show.connect(self._on_page_show)

    def refresh_spectrum_list(self) -> list:
        """刷新所有下拉列表中的光谱数据，按通道和类别过滤.

        保存并恢复当前选择，避免刷新时丢失用户选择。
        """
        spectra = self._spectrum_ctrl.list_spectra()
        self._spectra_summaries = {s.id: s for s in spectra}

        # Save current selections before repopulating
        saved_rgb = {ch: getattr(self, f"_rgb_sel_{ch}").current_id() for ch in ("R", "G", "B")}
        saved_filter = {
            ch: getattr(self, f"_filter_sel_{ch}").current_id() for ch in ("RCF", "GCF", "BCF")
        }
        saved_white = self._white_sel.current_id()

        # RGB selectors: only show LED/QD category (emission spectra)
        led_spectra = [s for s in spectra if s.category in ("LED", "QD")]
        for ch in ("R", "G", "B"):
            sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ch}")
            filtered = [(s.name, s.id) for s in led_spectra if s.channel == ch]
            sel.populate(filtered)

        # White selector: show all spectra
        all_items = [(s.name, s.id) for s in spectra]
        self._white_sel.populate(all_items)

        # Filter selectors (RCF/GCF/BCF): only show CF category spectra
        cf_spectra = [s for s in spectra if s.category == "CF"]
        for ch in ("RCF", "GCF", "BCF"):
            sel = getattr(self, f"_filter_sel_{ch}")
            # Filter by channel within CF: RCF→R, GCF→G, BCF→B
            channel_map = {"RCF": "R", "GCF": "G", "BCF": "B"}
            target_ch = channel_map[ch]
            filtered = [(s.name, s.id) for s in cf_spectra if s.channel == target_ch]
            sel.populate(filtered)

        # Restore selections
        for ch in ("R", "G", "B"):
            getattr(self, f"_rgb_sel_{ch}").set_current_id(saved_rgb[ch])
        for ch in ("RCF", "GCF", "BCF"):
            getattr(self, f"_filter_sel_{ch}").set_current_id(saved_filter[ch])
        self._white_sel.set_current_id(saved_white)

        return spectra

    def _auto_select_default_spectra(self, spectra: list) -> None:
        """如果当前未选择任何光谱，按通道自动选择默认光谱."""
        # Only auto-select on a completely fresh page.
        rgb_selected = any(
            getattr(self, f"_rgb_sel_{ch}").current_id() >= 0 for ch in ("R", "G", "B")
        )
        filter_selected = any(
            getattr(self, f"_filter_sel_{ch}").current_id() >= 0 for ch in ("RCF", "GCF", "BCF")
        )
        if rgb_selected or filter_selected:
            return

        channel_map = {
            "R": "R",
            "G": "G",
            "B": "B",
            "RCF": "R",
            "GCF": "G",
            "BCF": "B",
        }

        # Batch select to avoid repeated recalculation while UI is cold.
        for ui_ch, spec_ch in channel_map.items():
            if ui_ch in ("R", "G", "B"):
                # LED/QD emission spectra
                match = next(
                    (s for s in spectra if s.channel == spec_ch and s.category in ("LED", "QD")),
                    None,
                )
            else:
                # CF transmittance spectra
                match = next(
                    (s for s in spectra if s.channel == spec_ch and s.category == "CF"),
                    None,
                )
            if match is None:
                continue
            if ui_ch in ("R", "G", "B"):
                sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ui_ch}")
                sel._combo.blockSignals(True)
                sel.set_current_id(match.id)
                sel._combo.blockSignals(False)
                self._rgb_ids[ui_ch] = match.id
            else:
                sel = getattr(self, f"_filter_sel_{ui_ch}")
                sel._combo.blockSignals(True)
                sel.set_current_id(match.id)
                sel._combo.blockSignals(False)
                self._filter_ids[ui_ch] = match.id

        # Load the actual Spectrum DTOs once and then recalculate a single time.
        for ch in ("R", "G", "B"):
            sid = self._rgb_ids[ch]
            if sid >= 0:
                spec = self._spectrum_ctrl.get_spectrum(sid)
                if spec is not None:
                    self._spectra_cache[sid] = spec
                    self._original_spectra[ch] = spec

        for ch in ("RCF", "GCF", "BCF"):
            sid = self._filter_ids[ch]
            if sid >= 0:
                spec = self._spectrum_ctrl.get_spectrum(sid)
                if spec is not None:
                    self._spectra_cache[sid] = spec
                    self._filter_spectra[ch] = spec

        self._recalculate()

    # ------------------------------------------------------------------ #
    # 事件处理
    # ------------------------------------------------------------------ #

    def _on_page_show(self, page_index: int) -> None:
        """页面切换时立即刷新光谱列表，延迟执行自动选谱以保持侧边栏响应."""
        if page_index != self._page_index:
            return

        spectra = self.refresh_spectrum_list()

        if self._pending_auto_select:
            return

        self._pending_auto_select = True
        self._deferred_spectra = spectra
        # 50 ms delay lets the sidebar highlight and page frame render first,
        # so the click feels responsive even though the full calculation takes
        # a few hundred milliseconds.
        QTimer.singleShot(50, self._do_deferred_auto_select)

    def _do_deferred_auto_select(self) -> None:
        """执行延迟的默认光谱选择."""
        self._pending_auto_select = False
        spectra = self._deferred_spectra
        self._deferred_spectra = None
        if spectra is not None:
            self._auto_select_default_spectra(spectra)

    def _on_mode_changed(self, index: int) -> None:
        """计算模式切换."""
        self._mode = "white" if index == 1 else "rgb"
        self._update_visibility()
        self._recalculate()

    def _update_visibility(self) -> None:
        """根据当前模式切换 UI 可见性."""
        is_rgb = self._mode == "rgb"
        self._rgb_group_widget.setVisible(is_rgb)
        self._white_group_widget.setVisible(not is_rgb)
        # In white mode, LED R/G/B emission spectra are not available
        for key in ("R", "G", "B"):
            if key in self._compare_cbs:
                self._compare_cbs[key].setVisible(is_rgb)

    def _on_white_selection_changed(self) -> None:
        """白光光谱选择变化."""
        sid = self._white_sel.current_id()
        self._white_id = sid

        if sid >= 0:
            spec = self._spectrum_ctrl.get_spectrum(sid)
            if spec is not None:
                self._spectra_cache[sid] = spec
                self._white_spectrum = spec
            else:
                self._white_spectrum = None
        else:
            self._white_spectrum = None

        self._update_compare_checkbox_labels()
        self._recalculate()

    def _on_rgb_selection_changed(self, channel: str) -> None:
        """RGB 光谱选择变化."""
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

        self._update_compare_checkbox_labels()
        self._recalculate()

    def _on_filter_selection_changed(self, channel: str) -> None:
        """彩膜选择变化，自动填入光谱自带的膜厚值."""
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

            # 自动填入光谱自带的膜厚值（阻塞信号避免双重触发 _recalculate）
            summary = self._spectra_summaries.get(sid)
            if summary is not None and getattr(summary, "thickness_um", None) is not None:
                ctrl: _ThicknessControl = getattr(self, f"_thickness_{channel}")
                ctrl.block_signals(True)
                ctrl.set_value(summary.thickness_um)
                ctrl.block_signals(False)
                self._thickness[channel] = summary.thickness_um
        else:
            self._filter_spectra[channel] = None

        self._update_compare_checkbox_labels()
        self._recalculate()

    def _on_thickness_changed(self, channel: str, value: float) -> None:
        """厚度值变化."""
        self._thickness[channel] = value
        self._recalculate()

    def _on_paste(self) -> None:
        """Paste spectrum data from clipboard into the current project."""
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

        # Determine target selector and set channel/category accordingly
        target_ch: str | None = None
        target_category: str | None = None
        target_sel: _SpectrumSelector | None = None

        for ch in ("R", "G", "B"):
            sel: _SpectrumSelector = getattr(self, f"_rgb_sel_{ch}")
            if sel.underMouse():
                target_ch = ch
                target_category = "LED"
                target_sel = sel
                break
        if target_sel is None:
            for ch in ("RCF", "GCF", "BCF"):
                sel = getattr(self, f"_filter_sel_{ch}")
                if sel.underMouse():
                    target_ch = {"RCF": "R", "GCF": "G", "BCF": "B"}[ch]
                    target_category = "CF"
                    target_sel = sel
                    break

        sid = self._spectrum_ctrl.import_spectrum(
            spectrum,
            name="Pasted Spectrum",
            channel=target_ch,
            category=target_category,
        )
        if sid is None:
            return

        # Block signals during refresh to prevent double _recalculate
        self._refreshing = True
        self.refresh_spectrum_list()
        self._refreshing = False
        if target_sel is not None:
            # set_current_id triggers currentIndexChanged -> _on_filter_selection_changed
            # -> _recalculate, so no need to call target_callback explicitly
            target_sel.set_current_id(sid)
        elif self._white_group_widget.isVisible():
            self._white_sel.set_current_id(sid)
            self._on_white_selection_changed()

    def _on_reference_gamuts_changed(self) -> None:
        """更新参考色域显示."""
        selected = [name for name, cb in self._ref_gamut_cbs.items() if cb.isChecked()]
        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.set_reference_gamuts(selected)
            canvas.refresh()

    # ------------------------------------------------------------------ #
    # 核心计算
    # ------------------------------------------------------------------ #

    def _recalculate(self) -> None:
        """重新计算所有结果并刷新 UI."""
        if getattr(self, "_refreshing", False):
            return
        # Build active spectra dict without permanently overwriting _original_spectra
        if self._mode == "white":
            if self._white_spectrum is None:
                self._clear_results()
                return
            active_spectra = dict.fromkeys(("R", "G", "B"), self._white_spectrum)
        else:
            active_spectra = self._original_spectra

        if any(active_spectra[ch] is None for ch in ("R", "G", "B")):
            self._clear_results()
            return

        for ch in ("R", "G", "B"):
            filter_key = f"{ch}CF"
            original = active_spectra[ch]
            filter_spec = self._filter_spectra[filter_key]
            thickness = self._thickness[filter_key]

            if filter_spec is not None:
                self._filtered_spectra[ch] = self._apply_filter(original, filter_spec, thickness)
            else:
                self._filtered_spectra[ch] = None

        self._update_spectrum_preview()

        filtered_xys: dict[str, XY | None] = {}
        original_xys: dict[str, XY | None] = {}
        filtered_luminances: dict[str, float] = {}
        filtered_xyzs: dict[str, tuple[float, float, float] | None] = {}
        filtered_upvs: dict[str, tuple[float, float] | None] = {}

        for ch in ("R", "G", "B"):
            orig = active_spectra[ch]
            filt = self._filtered_spectra[ch]
            if orig is not None:
                try:
                    original_xys[ch] = self._color_ctrl.xy(orig)
                except Exception:  # noqa: BLE001
                    original_xys[ch] = None
            if filt is not None:
                try:
                    filtered_xys[ch] = self._color_ctrl.xy(filt)
                    filtered_luminances[ch] = self._color_ctrl.luminance(filt)
                    filtered_xyzs[ch] = self._xy_luminance_to_xyz(
                        filtered_xys[ch], filtered_luminances[ch]
                    )
                    filtered_upvs[ch] = self._color_ctrl.uprime_vprime(filt)
                except Exception:  # noqa: BLE001
                    filtered_xys[ch] = None
                    filtered_luminances[ch] = 0.0
                    filtered_xyzs[ch] = None
                    filtered_upvs[ch] = None

        white_xy: XY | None = None
        white_uprime_vprime: tuple[float, float] | None = None
        white_cct: float | None = None

        if all(filtered_xys.get(ch) is not None for ch in ("R", "G", "B")):
            try:
                xy_list = [filtered_xys[ch] for ch in ("R", "G", "B")]
                weights = [filtered_luminances[ch] for ch in ("R", "G", "B")]
                if sum(weights) > 0:
                    white_xy = self._color_ctrl.mix_xy(xy_list, weights=weights)
                else:
                    white_xy = self._color_ctrl.mix_xy(xy_list, weights=[1.0, 1.0, 1.0])
            except Exception:  # noqa: BLE001
                white_xy = None

        if white_xy is not None:
            try:
                white_spectrum = self._build_white_spectrum()
                if white_spectrum is not None:
                    white_uprime_vprime = self._color_ctrl.uprime_vprime(white_spectrum)
                    white_cct = self._color_ctrl.cct_mccamy(white_spectrum)
            except Exception:  # noqa: BLE001
                white_uprime_vprime = None
                white_cct = None

        self._update_cie_diagram(original_xys, filtered_xys, white_xy)
        self._update_chromaticity_data(
            filtered_xys,
            filtered_xyzs,
            filtered_upvs,
            white_xy,
            white_uprime_vprime,
            white_cct,
        )
        self._update_gamut_result(filtered_xys, white_xy)

        if all(
            v is not None
            for v in (filtered_xys.get("R"), filtered_xys.get("G"), filtered_xys.get("B"))
        ):
            for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
                canvas.add_trajectory_point("R", filtered_xys["R"])
                canvas.add_trajectory_point("G", filtered_xys["G"])
                canvas.add_trajectory_point("B", filtered_xys["B"])
                if white_xy is not None:
                    canvas.add_trajectory_point("W", white_xy)

        r_filt = filtered_xys.get("R")
        g_filt = filtered_xys.get("G")
        b_filt = filtered_xys.get("B")
        if all(v is not None for v in (r_filt, g_filt, b_filt)):
            self.white_point_calculated.emit(r_filt, g_filt, b_filt)

    def _apply_filter(
        self,
        original: Spectrum,
        filter_spec: Spectrum,
        thickness: float,
    ) -> Spectrum:
        """应用 Beer-Lambert Law: T = 10^(-alpha * d).

        CF spectra are transmittance (0~1) measured at a reference thickness
        d_ref (stored in filter_spec.meta["thickness_um"]). The absorption
        coefficient is alpha = -log10(T_ref) / d_ref, so the actual
        transmittance at thickness d is T = T_ref ^ (d / d_ref).

        If d_ref is missing, defaults to 1.0 um (legacy behavior).
        thickness=0 means no filter (transmittance = 100%).
        """
        if filter_spec is None or thickness <= 0:
            return original

        # Interpolate filter to original wavelength grid
        filter_values = np.interp(
            original.wavelengths,
            filter_spec.wavelengths,
            filter_spec.values,
        )

        # Clamp to (0, 1] to avoid log(0)
        filter_values = np.clip(filter_values, 1e-10, 1.0)

        # Get reference thickness from CF spectrum metadata
        d_ref = 1.0
        if filter_spec.meta:
            d_ref = filter_spec.meta.get("thickness_um", 1.0)
            if d_ref is None or d_ref <= 0:
                d_ref = 1.0

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
                "d_ref": d_ref,
            },
        )

    def _build_white_spectrum(self) -> Spectrum | None:
        """构建白点光谱（R + G + B 混合）."""
        spectra = []
        for ch in ("R", "G", "B"):
            spec = self._filtered_spectra.get(ch)
            if spec is None:
                return None
            spectra.append(spec)

        ref_wl = spectra[0].wavelengths
        mixed_values = np.zeros_like(ref_wl)
        for spec in spectra:
            aligned = np.interp(ref_wl, spec.wavelengths, spec.values)
            mixed_values = mixed_values + aligned

        return Spectrum(
            wavelengths=ref_wl.copy(),
            values=mixed_values,
            unit="a.u.",
            meta={"type": "white_point"},
        )

    @staticmethod
    def _xy_luminance_to_xyz(xy: XY, luminance_y: float) -> tuple[float, float, float]:
        """由 xy 色度坐标和亮度 Y 计算 XYZ 三刺激值.

        X = x * Y / y
        Y = luminance_y
        Z = (1 - x - y) * Y / y
        """
        if xy.y <= 0:
            return (0.0, 0.0, 0.0)
        x_val = xy.x * luminance_y / xy.y
        z_val = (1.0 - xy.x - xy.y) * luminance_y / xy.y
        return (x_val, luminance_y, z_val)

    # ------------------------------------------------------------------ #
    # UI 更新
    # ------------------------------------------------------------------ #

    def _clear_results(self) -> None:
        """清除所有结果显示."""
        self._filtered_chart.clear()
        self._original_chart.clear()
        self._compare_chart.clear()

        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.clear_all()

        # Re-apply reference gamuts after clear_all cleared them
        selected = [name for name, cb in self._ref_gamut_cbs.items() if cb.isChecked()]
        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.set_reference_gamuts(selected)
            canvas.refresh()

        for row in range(self._chromaticity_table.rowCount()):
            for col in range(1, self._chromaticity_table.columnCount()):
                item = self._chromaticity_table.item(row, col)
                if item is not None:
                    item.setText("--")

        for table in (self._gamut_table_1931, self._gamut_table_1976):
            for i in range(len(_STANDARD_GAMUTS)):
                for col in (1, 2):
                    item = table.item(i, col)
                    if item is not None:
                        item.setText("--")

    def _update_spectrum_preview(self) -> None:
        """更新光谱预览图."""
        self._filtered_chart.clear()
        filtered_items = [
            (spec, f"Filtered {ch}", _CHANNEL_COLORS[ch])
            for ch in ("R", "G", "B")
            if (spec := self._filtered_spectra.get(ch)) is not None
        ]
        if filtered_items:
            self._filtered_chart.plot_spectra(filtered_items)

        self._original_chart.clear()
        if self._mode == "white" and self._white_spectrum is not None:
            self._original_chart.plot_spectra([(self._white_spectrum, "White", "#FFFFFF")])
        else:
            original_items = [
                (spec, f"Original {ch}", _CHANNEL_COLORS[ch])
                for ch in ("R", "G", "B")
                if (spec := self._original_spectra.get(ch)) is not None
            ]
            if original_items:
                self._original_chart.plot_spectra(original_items)

        self._update_compare_chart()

    def _update_cie_diagram(
        self,
        original_xys: dict[str, XY | None],
        filtered_xys: dict[str, XY | None],
        white_xy: XY | None,
    ) -> None:
        """更新 CIE 色度图."""
        r_orig = original_xys.get("R")
        g_orig = original_xys.get("G")
        b_orig = original_xys.get("B")
        if all(v is not None for v in (r_orig, g_orig, b_orig)):
            for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
                canvas.set_original_rgb(
                    (r_orig.x, r_orig.y),
                    (g_orig.x, g_orig.y),
                    (b_orig.x, b_orig.y),
                )

        r_filt = filtered_xys.get("R")
        g_filt = filtered_xys.get("G")
        b_filt = filtered_xys.get("B")
        if all(v is not None for v in (r_filt, g_filt, b_filt)):
            wp_tuple = (white_xy.x, white_xy.y) if white_xy is not None else None
            for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
                canvas.set_filtered_rgb(
                    (r_filt.x, r_filt.y),
                    (g_filt.x, g_filt.y),
                    (b_filt.x, b_filt.y),
                    white_xy=wp_tuple,
                )

        # Always refresh so original RGB points are visible even without filter
        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.refresh()

    def _update_gamut_result(
        self,
        filtered_xys: dict[str, XY | None],
        white_xy: XY | None,
    ) -> None:
        """更新色域结果表格（1931 + 1976 两张表）."""
        r_xy = filtered_xys.get("R")
        g_xy = filtered_xys.get("G")
        b_xy = filtered_xys.get("B")

        if any(v is None for v in (r_xy, g_xy, b_xy)):
            for table in (self._gamut_table_1931, self._gamut_table_1976):
                for i in range(len(_STANDARD_GAMUTS)):
                    for col in (1, 2):
                        item = table.item(i, col)
                        if item is not None:
                            item.setText("--")
            return

        wp = white_xy if white_xy is not None else XY(x=0.3127, y=0.3290)
        device_gamut = self._color_ctrl.build_gamut_from_primaries_direct(
            name="device",
            red=r_xy,
            green=g_xy,
            blue=b_xy,
            white=wp,
        )

        for i, std_name in enumerate(_STANDARD_GAMUTS):
            try:
                self._color_ctrl.standard_gamut(std_name)
                cov_1931 = self._color_ctrl.coverage(std_name, device_gamut)
                mat_1931 = self._color_ctrl.match(std_name, device_gamut)
                cov_1976 = self._color_ctrl.coverage_1976(std_name, device_gamut)
                mat_1976 = self._color_ctrl.match_1976(std_name, device_gamut)
            except Exception:  # noqa: BLE001
                cov_1931 = 0.0
                mat_1931 = 0.0
                cov_1976 = 0.0
                mat_1976 = 0.0

            item = self._gamut_table_1931.item(i, 1)
            if item is not None:
                item.setText(f"{cov_1931:.2f}")
            item = self._gamut_table_1931.item(i, 2)
            if item is not None:
                item.setText(f"{mat_1931:.2f}")

            item = self._gamut_table_1976.item(i, 1)
            if item is not None:
                item.setText(f"{cov_1976:.2f}")
            item = self._gamut_table_1976.item(i, 2)
            if item is not None:
                item.setText(f"{mat_1976:.2f}")

    def _update_chromaticity_data(
        self,
        filtered_xys: dict[str, XY | None],
        filtered_xyzs: dict[str, tuple[float, float, float] | None],
        filtered_upvs: dict[str, tuple[float, float] | None],
        white_xy: XY | None,
        white_uprime_vprime: tuple[float, float] | None,
        white_cct: float | None,
    ) -> None:
        """更新 RGBW 色坐标 / XYZ / CCT 数据表 + RGB 光谱参数表."""

        def set_cell(
            table: QTableWidget, row: int, col: int, text: str
        ) -> None:
            item = table.item(row, col)
            if item is None:
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setItem(row, col, item)
            else:
                item.setText(text)

        for idx, ch in enumerate(("R", "G", "B")):
            xy = filtered_xys.get(ch)
            xyz = filtered_xyzs.get(ch)
            upv = filtered_upvs.get(ch)

            set_cell(self._chromaticity_table, idx, 1, f"{xy.x:.3f}" if xy is not None else "--")
            set_cell(self._chromaticity_table, idx, 2, f"{xy.y:.3f}" if xy is not None else "--")
            set_cell(
                self._chromaticity_table, idx, 3,
                f"{upv[0]:.3f}" if upv is not None else "--",
            )
            set_cell(
                self._chromaticity_table, idx, 4,
                f"{upv[1]:.3f}" if upv is not None else "--",
            )
            set_cell(
                self._chromaticity_table, idx, 5,
                f"{xyz[0]:.3f}" if xyz is not None else "--",
            )
            set_cell(
                self._chromaticity_table, idx, 6,
                f"{xyz[1]:.3f}" if xyz is not None else "--",
            )
            set_cell(self._chromaticity_table, idx, 7, "--")

        white_xyz_sum: tuple[float, float, float] | None = None
        if all(filtered_xyzs.get(ch) is not None for ch in ("R", "G", "B")):
            white_xyz_sum = tuple(
                sum(filtered_xyzs[ch][i] for ch in ("R", "G", "B")) for i in range(3)
            )

        set_cell(
            self._chromaticity_table, 3, 1,
            f"{white_xy.x:.3f}" if white_xy is not None else "--",
        )
        set_cell(
            self._chromaticity_table, 3, 2,
            f"{white_xy.y:.3f}" if white_xy is not None else "--",
        )
        set_cell(
            self._chromaticity_table, 3, 3,
            f"{white_uprime_vprime[0]:.3f}" if white_uprime_vprime is not None else "--",
        )
        set_cell(
            self._chromaticity_table, 3, 4,
            f"{white_uprime_vprime[1]:.3f}" if white_uprime_vprime is not None else "--",
        )
        set_cell(
            self._chromaticity_table, 3, 5,
            f"{white_xyz_sum[0]:.3f}" if white_xyz_sum is not None else "--",
        )
        set_cell(
            self._chromaticity_table, 3, 6,
            f"{white_xyz_sum[1]:.3f}" if white_xyz_sum is not None else "--",
        )
        set_cell(
            self._chromaticity_table, 3, 7,
            f"{white_cct:.0f} K" if white_cct is not None else "--",
        )

        self._update_spectrum_data_table()

    def _update_spectrum_data_table(self) -> None:
        """更新 RGB 光谱参数表（Peak / FWHM / Dominant λ / Purity）."""
        from colorlab_pro.engines.spectrum_analyzer import dominant_wavelength

        def set_cell(row: int, col: int, text: str) -> None:
            item = self._spectrum_data_table.item(row, col)
            if item is None:
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self._spectrum_data_table.setItem(row, col, item)
            else:
                item.setText(text)

        for idx, ch in enumerate(("R", "G", "B")):
            spec = self._filtered_spectra.get(ch)
            if spec is None:
                for col in range(1, 5):
                    set_cell(idx, col, "--")
                continue

            peak_idx = int(np.argmax(spec.values))
            peak_wl = float(spec.wavelengths[peak_idx])
            fwhm = self._compute_fwhm(spec)

            try:
                dom_wl = dominant_wavelength(spec)
            except Exception:  # noqa: BLE001
                dom_wl = None

            purity = self._compute_purity(spec)

            set_cell(idx, 1, f"{peak_wl:.0f}")
            set_cell(idx, 2, f"{fwhm:.0f}" if fwhm is not None else "--")
            set_cell(idx, 3, f"{dom_wl:.0f}" if dom_wl is not None else "--")
            set_cell(idx, 4, f"{purity:.3f}" if purity is not None else "--")

    def _compute_purity(self, spec: Spectrum) -> float | None:
        """Compute excitation purity for a filtered spectrum."""
        try:
            from colorlab_pro.engines.spectrum_analyzer import (
                _get_illuminant_xy,
                dominant_wavelength,
                xy,
            )

            xy_val = xy(spec)
            white = _get_illuminant_xy("E")
            dom_wl = dominant_wavelength(spec)
            if dom_wl is None:
                return None
            wavelengths = np.arange(380.0, 781.0, 1.0, dtype=np.float64)
            v = np.zeros_like(wavelengths)
            idx = int(dom_wl - 380.0)
            if 0 <= idx < v.size:
                v[idx] = 1.0
            s = Spectrum(wavelengths=wavelengths, values=v, unit="a.u.")
            locus_pt = xy(s)
            sample_vec = np.array([xy_val.x - white.x, xy_val.y - white.y])
            locus_vec = np.array([locus_pt.x - white.x, locus_pt.y - white.y])
            locus_norm = np.linalg.norm(locus_vec)
            if locus_norm < 1e-12:
                return None
            purity = float(np.linalg.norm(sample_vec) / locus_norm)
            return max(0.0, min(1.0, purity))
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _compute_fwhm(spec: Spectrum) -> float | None:
        """Compute Full Width at Half Maximum."""
        values = spec.values
        wavelengths = spec.wavelengths
        if values.size < 3:
            return None

        peak_val = float(np.max(values))
        if peak_val <= 0:
            return None

        half_max = peak_val / 2.0
        peak_idx = int(np.argmax(values))

        left_wl = None
        for i in range(peak_idx - 1, -1, -1):
            if values[i] < half_max:
                if i + 1 < values.size:
                    frac = (half_max - values[i]) / (values[i + 1] - values[i])
                    left_wl = wavelengths[i] + frac * (wavelengths[i + 1] - wavelengths[i])
                else:
                    left_wl = wavelengths[i]
                break

        right_wl = None
        for i in range(peak_idx + 1, values.size):
            if values[i] < half_max:
                frac = (half_max - values[i - 1]) / (values[i] - values[i - 1])
                right_wl = wavelengths[i - 1] + frac * (wavelengths[i] - wavelengths[i - 1])
                break

        if left_wl is not None and right_wl is not None:
            return float(right_wl - left_wl)
        return None
