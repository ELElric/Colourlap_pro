"""Unit tests for SpectrumImportWidget."""

from __future__ import annotations

import numpy as np
import pytest

from colorlab_pro.ui.widgets.spectrum_import import SpectrumImportWidget


def test_parse_valid_text(qtbot):
    widget = SpectrumImportWidget()
    qtbot.addWidget(widget)
    spectrum = widget._parse_text("400 0.1\n500 0.5\n600 0.8")
    np.testing.assert_array_equal(spectrum.wavelengths, [400.0, 500.0, 600.0])
    np.testing.assert_array_equal(spectrum.values, [0.1, 0.5, 0.8])


def test_parse_ignores_comments_and_empty_lines(qtbot):
    widget = SpectrumImportWidget()
    qtbot.addWidget(widget)
    spectrum = widget._parse_text("# header\n\n400 0.1\n500 0.5")
    np.testing.assert_array_equal(spectrum.wavelengths, [400.0, 500.0])


def test_parse_too_few_points_raises(qtbot):
    widget = SpectrumImportWidget()
    qtbot.addWidget(widget)
    with pytest.raises(ValueError, match="At least two"):
        widget._parse_text("400 0.1")


def test_parse_invalid_row_raises(qtbot):
    widget = SpectrumImportWidget()
    qtbot.addWidget(widget)
    with pytest.raises(ValueError, match="Invalid numeric row"):
        widget._parse_text("400 abc")


def test_import_button_emits_spectrum(qtbot):
    widget = SpectrumImportWidget()
    qtbot.addWidget(widget)
    widget._editor.setPlainText("400 0.1\n500 0.5\n600 0.8")
    widget._parse_button.click()

    received = []
    widget.import_requested.connect(lambda s: received.append(s))
    widget._import_button.click()

    assert len(received) == 1
    np.testing.assert_array_equal(received[0].wavelengths, [400.0, 500.0, 600.0])
