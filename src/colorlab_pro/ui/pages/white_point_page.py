"""WhitePointPage -- 白点计算页面.

提供两种计算模式：
1. Forward Calculation（正向计算）：
   输入 RGB 坐标 (x,y) + RGB 比例，输出白点 (x, y)
2. Reverse Calculation（反向计算）：
   输入 RGB 坐标 (x,y) + 目标白点 (x,y)，输出 R/G/B 比例
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.dto.color import XY
from colorlab_pro.ui.widgets.cie_diagram import CIECanvas


class WhitePointPage(QWidget):
    """White Point 白点计算页面."""

    white_point_calculated = Signal(object)

    def __init__(
        self,
        color_controller: ColorController | None = None,
        page_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if color_controller is None:
            raise ValueError("color_controller must not be None")
        self._color_ctrl = color_controller
        self._page_index = page_index
        self._updating = False

        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)

        self._build_mode_selection(outer_layout)

        row1_splitter = QSplitter(Qt.Orientation.Horizontal)
        row1_splitter.setChildrenCollapsible(False)
        row1_splitter.setHandleWidth(6)
        row1_splitter.setOpaqueResize(False)

        self._build_input_table(row1_splitter)
        self._build_gamut_results(row1_splitter)
        row1_splitter.setSizes([350, 650])
        outer_layout.addWidget(row1_splitter, stretch=0)

        row2_splitter = QSplitter(Qt.Orientation.Horizontal)
        row2_splitter.setChildrenCollapsible(False)
        row2_splitter.setHandleWidth(6)
        row2_splitter.setOpaqueResize(False)

        self._cie_xy_canvas = CIECanvas(mode="xy")
        self._cie_xy_canvas.set_reference_gamuts(["sRGB", "NTSC", "DCI-P3", "BT2020"])
        self._cie_xy_canvas.setMinimumHeight(280)
        row2_splitter.addWidget(self._cie_xy_canvas)

        self._cie_uv_canvas = CIECanvas(mode="uv")
        self._cie_uv_canvas.set_reference_gamuts(["sRGB", "NTSC", "DCI-P3", "BT2020"])
        self._cie_uv_canvas.setMinimumHeight(280)
        row2_splitter.addWidget(self._cie_uv_canvas)

        row2_splitter.setSizes([380, 380])
        outer_layout.addWidget(row2_splitter, stretch=3)

    def _build_mode_selection(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Mode Selection")
        mode_layout = QHBoxLayout(group)
        self._forward_radio = QRadioButton("Forward Calculation")
        self._reverse_radio = QRadioButton("Reverse Calculation")
        self._forward_radio.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._forward_radio, 0)
        self._mode_group.addButton(self._reverse_radio, 1)
        mode_layout.addWidget(self._forward_radio)
        mode_layout.addWidget(self._reverse_radio)
        mode_layout.addStretch()

        self._gamut_checks: dict[str, QCheckBox] = {}
        for name in ("sRGB", "NTSC", "DCI-P3", "BT2020"):
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.toggled.connect(self._on_gamut_check_toggled)
            self._gamut_checks[name] = cb
            mode_layout.addWidget(cb)

        parent_layout.addWidget(group)

    def _build_input_table(self, parent: QWidget) -> None:
        group = QGroupBox("RGBW Input")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 10, 6, 6)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setRowCount(4)
        self._table.setHorizontalHeaderLabels(["Ch", "x", "y", "Ratio"])
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 36)
        self._table.verticalHeader().setDefaultSectionSize(32)

        self._table.setMinimumHeight(130)
        layout.addWidget(self._table)

        for row, ch in enumerate(("R", "G", "B", "W")):
            ch_item = QTableWidgetItem(ch)
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ch_item.setFlags(ch_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, ch_item)

            for col, default in ((1, ""), (2, ""), (3, "0.3333" if row < 3 else "--")):
                item = QTableWidgetItem(default)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)

        self._apply_mode("forward")
        self._table.cellChanged.connect(self._on_cell_changed)
        parent.addWidget(group)

    def _apply_mode(self, mode: str) -> None:
        self._updating = True
        for row in range(4):
            for col in (1, 2):
                item = self._table.item(row, col)
                if mode == "forward" and row == 3:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(Qt.GlobalColor.darkGray)
                else:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(Qt.BrushStyle.NoBrush)
            item = self._table.item(row, 3)
            if row == 3 or mode == "reverse":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(Qt.GlobalColor.darkGray)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setBackground(Qt.BrushStyle.NoBrush)
        self._updating = False

    def _build_gamut_results(self, parent: QWidget) -> None:
        group = QGroupBox("Gamut Results")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 10, 6, 6)
        self._gamut_table = QTableWidget()
        self._gamut_table.setColumnCount(5)
        self._gamut_table.setHorizontalHeaderLabels([
            "Standard", "Coverage 1931 (%)", "Match 1931 (%)",
            "Coverage 1976 (%)", "Match 1976 (%)",
        ])
        self._gamut_table.setRowCount(4)
        self._gamut_table.verticalHeader().setVisible(False)
        self._gamut_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._gamut_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        for i, name in enumerate(("sRGB", "NTSC", "DCI-P3", "BT2020")):
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._gamut_table.setItem(i, 0, item)
            for col in (1, 2, 3, 4):
                dash = QTableWidgetItem("--")
                dash.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._gamut_table.setItem(i, col, dash)
        header = self._gamut_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._gamut_table.setMinimumHeight(130)
        layout.addWidget(self._gamut_table)
        parent.addWidget(group)

    def _wire_signals(self) -> None:
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

    def connect_auto_refresh(self, window) -> None:
        window.page_about_to_show.connect(self._on_page_show)

    def set_rgb_coordinates(self, r_xy: XY, g_xy: XY, b_xy: XY) -> None:
        current = self._get_rgb_xy()
        if all(c is None for c in current):
            self._updating = True
            self._table.item(0, 1).setText(f"{r_xy.x:.3f}")
            self._table.item(0, 2).setText(f"{r_xy.y:.3f}")
            self._table.item(1, 1).setText(f"{g_xy.x:.3f}")
            self._table.item(1, 2).setText(f"{g_xy.y:.3f}")
            self._table.item(2, 1).setText(f"{b_xy.x:.3f}")
            self._table.item(2, 2).setText(f"{b_xy.y:.3f}")
            self._updating = False
            self._on_calculate()

    def get_rgb_coordinates(self) -> tuple[XY | None, XY | None, XY | None]:
        return self._get_rgb_xy()

    def _get_rgb_xy(self) -> tuple[XY | None, XY | None, XY | None]:
        result = []
        for row in range(3):
            result.append(self._parse_xy(row))
        return tuple(result)

    def _get_w_xy(self) -> XY | None:
        return self._parse_xy(3)

    def _get_ratios(self) -> tuple[float, float, float]:
        return tuple(self._parse_ratio(row) for row in range(3))

    def _parse_xy(self, row: int) -> XY | None:
        try:
            x = float(self._table.item(row, 1).text().strip())
            y = float(self._table.item(row, 2).text().strip())
        except (ValueError, AttributeError):
            return None
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return None
        return XY(x=x, y=y)

    def _parse_ratio(self, row: int) -> float:
        try:
            return float(self._table.item(row, 3).text().strip())
        except (ValueError, AttributeError):
            return 0.3333

    def _on_page_show(self, page_index: int) -> None:
        pass

    def _on_mode_changed(self, button) -> None:
        if button == self._forward_radio:
            self._apply_mode("forward")
        else:
            self._apply_mode("reverse")
        self._on_calculate()

    def _get_visible_gamuts(self) -> list[str]:
        return [name for name, cb in self._gamut_checks.items() if cb.isChecked()]

    def _on_gamut_check_toggled(self) -> None:
        visible = self._get_visible_gamuts()
        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.set_reference_gamuts(visible)
            canvas.refresh()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating:
            return
        if col == 0:
            return
        self._on_calculate()

    def _on_calculate(self) -> None:
        if self._forward_radio.isChecked():
            self._calculate_forward()
        else:
            self._calculate_reverse()

    def _calculate_forward(self) -> None:
        r_xy, g_xy, b_xy = self._get_rgb_xy()
        if any(v is None for v in (r_xy, g_xy, b_xy)):
            self._clear_results()
            return
        r_ratio, g_ratio, b_ratio = self._get_ratios()
        total = r_ratio + g_ratio + b_ratio
        if total <= 0:
            self._clear_results()
            return
        r_ratio /= total
        g_ratio /= total
        b_ratio /= total
        try:
            white_xy = self._color_ctrl.mix_xy(
                [r_xy, g_xy, b_xy],
                weights=[r_ratio, g_ratio, b_ratio],
            )
        except Exception as exc:  # noqa: BLE001
            self._clear_results()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Calculation Error", str(exc))
            return
        self._updating = True
        self._table.item(3, 1).setText(f"{white_xy.x:.3f}")
        self._table.item(3, 2).setText(f"{white_xy.y:.3f}")
        self._updating = False
        self._update_gamut_analysis(r_xy, g_xy, b_xy, white_xy)
        self.white_point_calculated.emit({"xy": white_xy})

    def _calculate_reverse(self) -> None:
        r_xy, g_xy, b_xy = self._get_rgb_xy()
        if any(v is None for v in (r_xy, g_xy, b_xy)):
            self._clear_results()
            return
        target_xy = self._get_w_xy()
        if target_xy is None:
            self._clear_results()
            return
        try:
            import colour
            from scipy.optimize import nnls

            xy_list = [r_xy, g_xy, b_xy]
            design_matrix = np.zeros((3, 3), dtype=np.float64)
            for i, p in enumerate(xy_list):
                xyz_arr = colour.xy_to_XYZ(np.array([p.x, p.y]))
                design_matrix[:, i] = xyz_arr
            b = np.array([target_xy.x, target_xy.y, 1.0 - target_xy.x - target_xy.y], dtype=np.float64)
            w, _ = nnls(design_matrix, b)
            total_w = float(np.sum(w))
            if total_w <= 1e-12:
                self._clear_results()
                return
            weights = w / total_w
            achieved = self._color_ctrl.mix_xy(xy_list, weights=weights.tolist())
            self._updating = True
            self._table.item(0, 3).setText(f"{weights[0]:.3f}")
            self._table.item(1, 3).setText(f"{weights[1]:.3f}")
            self._table.item(2, 3).setText(f"{weights[2]:.3f}")
            self._updating = False
            self._update_gamut_analysis(r_xy, g_xy, b_xy, achieved)
        except Exception:  # noqa: BLE001
            self._clear_results()

    def _clear_results(self) -> None:
        self._updating = True
        self._table.item(3, 1).setText("")
        self._table.item(3, 2).setText("")
        self._updating = False
        self._clear_gamut_analysis()

    def _update_gamut_analysis(self, r_xy: XY, g_xy: XY, b_xy: XY, white_xy: XY) -> None:
        if not hasattr(self, "_cie_xy_canvas"):
            return
        device_gamut = self._color_ctrl.build_gamut_from_primaries_direct(
            name="Device", red=r_xy, green=g_xy, blue=b_xy, white=white_xy,
        )
        standard_names = ["sRGB", "NTSC", "DCI-P3", "BT2020"]
        for row, name in enumerate(standard_names):
            try:
                cov_1931 = self._color_ctrl.coverage(name, device_gamut)
                mat_1931 = self._color_ctrl.match(name, device_gamut)
                cov_1976 = self._color_ctrl.coverage_1976(name, device_gamut)
                mat_1976 = self._color_ctrl.match_1976(name, device_gamut)
            except Exception:  # noqa: BLE001
                cov_1931 = mat_1931 = cov_1976 = mat_1976 = None
            self._gamut_table.item(row, 1).setText(f"{cov_1931:.2f}" if cov_1931 is not None else "--")
            self._gamut_table.item(row, 2).setText(f"{mat_1931:.2f}" if mat_1931 is not None else "--")
            self._gamut_table.item(row, 3).setText(f"{cov_1976:.2f}" if cov_1976 is not None else "--")
            self._gamut_table.item(row, 4).setText(f"{mat_1976:.2f}" if mat_1976 is not None else "--")

        r_pt = (r_xy.x, r_xy.y)
        g_pt = (g_xy.x, g_xy.y)
        b_pt = (b_xy.x, b_xy.y)
        w_pt = (white_xy.x, white_xy.y)
        visible = self._get_visible_gamuts()
        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.clear_all()
            canvas.set_original_rgb(r_pt, g_pt, b_pt, white_xy=w_pt)
            canvas.set_filtered_rgb(r_pt, g_pt, b_pt, white_xy=w_pt)
            canvas.set_show_original(True)
            canvas.set_show_filtered(False)
            canvas.set_show_white_point(True)
            canvas.set_show_trajectory(False)
            canvas.set_show_triangle(True)
            canvas.set_reference_gamuts(visible)
            canvas.refresh()

    def _clear_gamut_analysis(self) -> None:
        if not hasattr(self, "_cie_xy_canvas"):
            return
        self._cie_xy_canvas.clear_all()
        self._cie_uv_canvas.clear_all()
        visible = self._get_visible_gamuts()
        for canvas in (self._cie_xy_canvas, self._cie_uv_canvas):
            canvas.set_reference_gamuts(visible)
            canvas.refresh()
        for row in range(self._gamut_table.rowCount()):
            for col in range(1, self._gamut_table.columnCount()):
                self._gamut_table.item(row, col).setText("--")
