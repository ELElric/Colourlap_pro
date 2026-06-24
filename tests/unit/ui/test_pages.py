"""Unit tests for page widgets."""

from __future__ import annotations

from colorlab_pro.dto.color import XY, OptimizationResult
from colorlab_pro.ui.widgets.pages import (
    AnalysisResultWidget,
    ColorMixingResultWidget,
    ExportOptionsWidget,
    GamutResultWidget,
    OptimizationResultWidget,
)


def test_analysis_result_widget(qtbot):
    widget = AnalysisResultWidget()
    qtbot.addWidget(widget)
    widget.set_results((1.0, 2.0, 3.0), (0.3, 0.4), 6500.0, 620.5)
    assert "1.000" in widget._xyz.text()
    assert "6500" in widget._cct.text()
    assert "620" in widget._dominant.text()


def test_color_mixing_result_widget(qtbot):
    widget = ColorMixingResultWidget()
    qtbot.addWidget(widget)
    widget.set_results((1.0, 2.0, 3.0), (0.3, 0.4))
    assert "0.300" in widget._mixed_xy.text()


def test_gamut_result_widget(qtbot):
    widget = GamutResultWidget()
    qtbot.addWidget(widget)
    widget.set_results("sRGB", 100.0, 99.5)
    assert widget._target.text() == "sRGB"
    assert widget._coverage.text() == "100.00"


def test_optimization_result_widget(qtbot):
    widget = OptimizationResultWidget()
    qtbot.addWidget(widget)
    result = OptimizationResult(
        thicknesses_um=[1.0, 2.0],
        achieved_xy=XY(x=0.3, y=0.3),
        target_xy=XY(x=0.3127, y=0.3290),
        delta_xy=0.01,
        converged=True,
        iterations=10,
        meta={},
    )
    widget.set_result(result)
    assert "Converged: True" in widget._summary.text()


def test_export_options_widget(qtbot):
    widget = ExportOptionsWidget()
    qtbot.addWidget(widget)
    assert widget.formats() == ["CSV", "XLSX", "JSON"]
