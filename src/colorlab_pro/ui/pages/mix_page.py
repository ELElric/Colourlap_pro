"""MixPage — workspace page for spectrum mixing."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.viewmodels.mix_viewmodel import MixViewModel
from colorlab_pro.ui.widgets.spectrum_chart import SpectrumChartWidget


class MixPage(QWidget):
    """Workspace page for mixing spectra.

    Automatically mixes when 2+ spectra are added and supports per-spectrum
    adjustable weights.
    """

    def __init__(
        self,
        controller: ColorController,
        page_index: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize with a ColorController.

        Args:
            controller: The color controller for mix operations.
            page_index: Index of this page in the main window stack.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._page_index = page_index
        self._view_model = MixViewModel(controller, parent=self)
        self._weight_spinboxes: list[QDoubleSpinBox] = []
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        """Construct the page layout."""
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Mix Spectra</h3>"))
        header.addWidget(QLabel("<i>Auto-mix when 2+ spectra are added</i>"))
        header.addStretch()

        self._clear_btn = QPushButton("Clear All")
        header.addWidget(self._clear_btn)
        layout.addLayout(header)

        # Spectrum list
        self._list = QListWidget()
        layout.addWidget(self._list)

        # Adjustable weights
        weights_group = QWidget()
        weights_layout = QVBoxLayout(weights_group)
        weights_layout.setContentsMargins(0, 0, 0, 0)
        weights_layout.addWidget(QLabel("<b>Weights</b>"))
        self._weights_form = QFormLayout()
        self._weights_form.setVerticalSpacing(2)
        weights_layout.addLayout(self._weights_form)
        layout.addWidget(weights_group)

        # Mix chart
        self._chart = SpectrumChartWidget()
        self._chart.setMinimumHeight(200)
        layout.addWidget(self._chart)

        # Result area (auto-updated)
        self._result_label = QLabel("Add spectra from the Spectrum page.")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        # Status
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def _wire_signals(self) -> None:
        """Connect UI signals to ViewModel actions."""
        self._clear_btn.clicked.connect(self._view_model.clear_spectra)
        self._view_model.selection_changed.connect(self._on_selection_changed)
        self._view_model.mix_result_changed.connect(self._on_mix_result)
        self._view_model.error_occurred.connect(
            lambda msg: self._status_label.setText(f"Error: {msg}")
        )
        self._view_model.status_changed.connect(lambda msg: self._status_label.setText(msg))

    def connect_auto_refresh(self, window) -> None:
        """Connect to MainWindow.page_about_to_show for auto-refresh on page switch."""
        window.page_about_to_show.connect(self._on_page_show)

    def _on_page_show(self, page_index: int) -> None:
        """Auto-refresh when this page becomes visible."""
        if page_index == self._page_index:
            self._on_selection_changed(self._view_model.selected_spectra)

    def _on_selection_changed(self, spectra: list[Spectrum]) -> None:
        """Update UI when ViewModel selection changes. Auto-mix if 2+ spectra."""
        self._list.clear()
        # Rebuild weight spinboxes
        self._weight_spinboxes.clear()
        while self._weights_form.rowCount():
            self._weights_form.removeRow(0)

        for i, spec in enumerate(spectra):
            name = spec.meta.get("name", f"Spectrum {i + 1}") if spec.meta else f"Spectrum {i + 1}"
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(item)

            spin = QDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.1)
            weight = self._view_model.weights[i] if i < len(self._view_model.weights) else 1.0
            spin.setValue(weight)
            spin.valueChanged.connect(lambda value, idx=i: self._on_weight_changed(idx, value))
            self._weight_spinboxes.append(spin)
            self._weights_form.addRow(f"{name}:", spin)

        # Update chart
        self._chart.clear()
        if spectra:
            labels = [
                (s.meta.get("name", f"Spectrum {i + 1}") if s.meta else f"Spectrum {i + 1}")
                for i, s in enumerate(spectra)
            ]
            self._chart.plot_multiple(spectra, labels=labels)

        # Auto-mix when 2+ spectra
        if len(spectra) >= 2:
            self._view_model.mix()
        else:
            self._result_label.setText(
                "Add spectra from the Spectrum page."
                if len(spectra) == 0
                else "Add one more spectrum to auto-mix."
            )

    def _on_weight_changed(self, index: int, value: float) -> None:
        """Update the model weight and re-mix."""
        self._view_model.set_weight(index, value)
        if len(self._view_model.selected_spectra) >= 2:
            self._view_model.mix()

    def _on_mix_result(self, result) -> None:
        """Display mix results."""
        if result is None:
            self._result_label.setText("No result.")
            return
        self._result_label.setText(
            f"Mixed XYZ: ({result.xyz.X:.4f}, {result.xyz.Y:.4f}, {result.xyz.Z:.4f})  |  "
            f"xy: ({result.xy.x:.4f}, {result.xy.y:.4f})"
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def add_spectrum(self, spectrum: Spectrum) -> None:
        """Add a spectrum to the mix."""
        self._view_model.add_spectrum(spectrum)
