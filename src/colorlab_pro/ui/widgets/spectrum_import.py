"""SpectrumImport widget parses tabular spectrum data from pasted text."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.dto.spectrum import Spectrum


class SpectrumImportWidget(QWidget):
    """Widget that lets the user paste wavelength/value pairs and import them."""

    import_requested = Signal(Spectrum)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the widget."""
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Create the editor and import button."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Paste wavelength and value pairs (nm, a.u.):", self))

        self._editor = QPlainTextEdit(self)
        self._editor.setPlaceholderText("400 0.1\n500 0.5\n600 0.8")
        layout.addWidget(self._editor)

        toolbar = QHBoxLayout()
        self._parse_button = QPushButton("Parse", self)
        self._parse_button.clicked.connect(self._on_parse)
        toolbar.addWidget(self._parse_button)

        self._import_button = QPushButton("Import", self)
        self._import_button.setEnabled(False)
        self._import_button.clicked.connect(self._on_import)
        toolbar.addWidget(self._import_button)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._status = QLabel("", self)
        layout.addWidget(self._status)

        self._pending_spectrum: Spectrum | None = None

    def _on_parse(self) -> None:
        """Parse the text and preview the resulting spectrum."""
        try:
            self._pending_spectrum = self._parse_text(self._editor.toPlainText())
            self._status.setText(f"Parsed {len(self._pending_spectrum.wavelengths)} points.")
            self._import_button.setEnabled(True)
        except ValueError as exc:
            self._status.setText(f"Parse error: {exc}")
            self._import_button.setEnabled(False)
            self._pending_spectrum = None

    def _on_import(self) -> None:
        """Emit the parsed spectrum for import."""
        if self._pending_spectrum is not None:
            self.import_requested.emit(self._pending_spectrum)
            self._editor.clear()
            self._pending_spectrum = None
            self._import_button.setEnabled(False)
            self._status.setText("Imported.")

    @staticmethod
    def _parse_text(text: str) -> Spectrum:
        """Parse rows of numeric data into a Spectrum DTO."""
        wavelengths: list[float] = []
        values: list[float] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                raise ValueError(f"Each row needs at least two numbers: {line}")
            try:
                wavelengths.append(float(parts[0]))
                values.append(float(parts[1]))
            except ValueError as exc:
                raise ValueError(f"Invalid numeric row: {line}") from exc

        if len(wavelengths) < 2:
            raise ValueError("At least two data points are required")

        return Spectrum(
            wavelengths=np.array(wavelengths, dtype=np.float64),
            values=np.array(values, dtype=np.float64),
            unit="a.u.",
        )
