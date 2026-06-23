"""Tests for SpectrumChartWidget."""

from __future__ import annotations

import numpy as np

from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.widgets.spectrum_chart import SpectrumChartWidget


class TestSpectrumChartWidget:
    def test_creation(self, qtbot) -> None:
        widget = SpectrumChartWidget()
        qtbot.addWidget(widget)
        assert widget._canvas is not None

    def test_plot_spectrum(self, qtbot) -> None:
        widget = SpectrumChartWidget()
        qtbot.addWidget(widget)
        spec = Spectrum(
            wavelengths=np.array([400.0, 500.0, 600.0]),
            values=np.array([0.1, 0.5, 0.9]),
        )
        widget.plot_spectrum(spec, label="Test")
        lines = widget._ax.get_lines()
        assert len(lines) == 1

    def test_plot_multiple(self, qtbot) -> None:
        widget = SpectrumChartWidget()
        qtbot.addWidget(widget)
        s1 = Spectrum(wavelengths=np.array([400.0, 500.0]), values=np.array([0.1, 0.5]))
        s2 = Spectrum(wavelengths=np.array([400.0, 500.0]), values=np.array([0.2, 0.4]))
        widget.plot_multiple([s1, s2], labels=["A", "B"])
        lines = widget._ax.get_lines()
        assert len(lines) == 2

    def test_clear(self, qtbot) -> None:
        widget = SpectrumChartWidget()
        qtbot.addWidget(widget)
        spec = Spectrum(wavelengths=np.array([400.0]), values=np.array([0.1]))
        widget.plot_spectrum(spec)
        widget.clear()
        lines = widget._ax.get_lines()
        assert len(lines) == 0
