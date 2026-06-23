"""AnalyzePage — workspace page for spectrum analysis."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.ui.viewmodels.analyze_viewmodel import AnalyzeViewModel
from colorlab_pro.ui.widgets.spectrum_chart import SpectrumChartWidget


class AnalyzePage(QWidget):
    """Workspace page for analyzing spectra."""

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize with controller references.

        Args:
            spectrum_controller: For spectrum data operations.
            color_controller: For colorimetric helpers.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._spectrum_ctrl = spectrum_controller
        self._view_model = AnalyzeViewModel(spectrum_controller, color_controller, parent=self)
        self._last_result: dict = {}
        self._build_ui()
        self._wire_signals()
        self._populate_gamut_combos()

    def _build_ui(self) -> None:
        """Construct the page layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Analyze</h3>"))
        header.addStretch()

        header.addWidget(QLabel("Show:"))
        self._display_mode = QComboBox()
        self._display_mode.addItems(["xy + u'v'", "xy only", "u'v' only"])
        header.addWidget(self._display_mode)

        header.addWidget(QLabel("Observer:"))
        self._observer_combo = QComboBox()
        self._observer_combo.addItems(self._view_model.observers())
        header.addWidget(self._observer_combo)

        header.addWidget(QLabel("Illuminant:"))
        self._illuminant_combo = QComboBox()
        self._illuminant_combo.addItems(self._view_model.illuminants())
        self._illuminant_combo.setCurrentText("D65")
        header.addWidget(self._illuminant_combo)

        self._analyze_btn = QPushButton("Analyze Selected")
        self._analyze_btn.setEnabled(False)
        header.addWidget(self._analyze_btn)
        layout.addLayout(header)

        # Spectrum chart
        self._chart = SpectrumChartWidget()
        self._chart.setMinimumHeight(200)
        layout.addWidget(self._chart)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setMaximumHeight(160)
        self._result_text.setPlaceholderText("Select a spectrum to analyze.")
        layout.addWidget(self._result_text)

        # Coverage / Match section
        gamut_group = QGroupBox("Coverage / Match")
        gamut_layout = QVBoxLayout(gamut_group)

        form = QFormLayout()
        self._target_gamut_combo = QComboBox()
        self._device_gamut_combo = QComboBox()
        form.addRow("Target Gamut", self._target_gamut_combo)
        form.addRow("Device Gamut", self._device_gamut_combo)
        gamut_layout.addLayout(form)

        self._compare_btn = QPushButton("Compare Gamuts")
        gamut_layout.addWidget(self._compare_btn)

        self._gamut_result_label = QLabel("Select two gamuts and click Compare.")
        self._gamut_result_label.setWordWrap(True)
        gamut_layout.addWidget(self._gamut_result_label)

        # Spectrum vs Gamut subsection
        vs_layout = QHBoxLayout()
        vs_layout.addWidget(QLabel("Spectrum vs Gamut:"))
        self._spectrum_gamut_combo = QComboBox()
        vs_layout.addWidget(self._spectrum_gamut_combo)
        self._spectrum_gamut_btn = QPushButton("Check")
        self._spectrum_gamut_btn.setEnabled(False)
        vs_layout.addWidget(self._spectrum_gamut_btn)
        vs_layout.addStretch()
        gamut_layout.addLayout(vs_layout)

        self._spectrum_gamut_label = QLabel("No spectrum selected.")
        self._spectrum_gamut_label.setWordWrap(True)
        gamut_layout.addWidget(self._spectrum_gamut_label)

        layout.addWidget(gamut_group)

        # Delta E section
        delta_group = QGroupBox("Delta E")
        delta_layout = QVBoxLayout(delta_group)

        delta_form = QFormLayout()
        self._delta_ref_combo = QComboBox()
        self._delta_method_combo = QComboBox()
        self._delta_method_combo.addItems(self._view_model.delta_e_methods())
        delta_form.addRow("Reference Spectrum", self._delta_ref_combo)
        delta_form.addRow("Method", self._delta_method_combo)
        delta_layout.addLayout(delta_form)

        self._delta_btn = QPushButton("Compute Delta E")
        self._delta_btn.setEnabled(False)
        delta_layout.addWidget(self._delta_btn)

        self._delta_result_label = QLabel("Select a target spectrum and a reference.")
        self._delta_result_label.setWordWrap(True)
        delta_layout.addWidget(self._delta_result_label)

        layout.addWidget(delta_group)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def _wire_signals(self) -> None:
        """Connect UI signals."""
        self._analyze_btn.clicked.connect(self._on_analyze)
        self._display_mode.currentIndexChanged.connect(
            lambda: self._on_analysis_changed(self._last_result)
        )
        self._observer_combo.currentIndexChanged.connect(self._reanalyze)
        self._illuminant_combo.currentIndexChanged.connect(self._reanalyze)
        self._compare_btn.clicked.connect(self._on_compare_gamuts)
        self._spectrum_gamut_btn.clicked.connect(self._on_spectrum_vs_gamut)
        self._delta_btn.clicked.connect(self._on_delta_e)

        self._view_model.analysis_changed.connect(self._on_analysis_changed)
        self._view_model.target_changed.connect(self._on_target_changed)
        self._view_model.error_occurred.connect(
            lambda msg: self._status_label.setText(f"Error: {msg}")
        )
        self._view_model.status_changed.connect(lambda msg: self._status_label.setText(msg))

    def _populate_gamut_combos(self) -> None:
        """Fill gamut dropdowns from the controller."""
        names = self._view_model.standard_gamuts()
        for combo in (
            self._target_gamut_combo,
            self._device_gamut_combo,
            self._spectrum_gamut_combo,
        ):
            combo.clear()
            combo.addItems(names)
        if "sRGB" in names:
            self._target_gamut_combo.setCurrentText("sRGB")
        if "DCI-P3" in names:
            self._device_gamut_combo.setCurrentText("DCI-P3")

    def _on_target_changed(self, spectrum) -> None:
        """Enable analysis and gamut checks when a target spectrum is set."""
        self._analyze_btn.setEnabled(spectrum is not None)
        self._spectrum_gamut_btn.setEnabled(spectrum is not None)
        self._delta_btn.setEnabled(spectrum is not None)
        self._populate_delta_reference_combo()
        if spectrum is None:
            self._spectrum_gamut_label.setText("No spectrum selected.")

    def _populate_delta_reference_combo(self) -> None:
        """Fill the Delta E reference combo with project spectra."""
        self._delta_ref_combo.clear()
        target_id = self._view_model.target_id
        for summary in self._spectrum_ctrl.list_spectra():
            if summary.id == target_id:
                continue
            self._delta_ref_combo.addItem(summary.name, summary.id)

    def _on_analyze(self) -> None:
        """Trigger analysis on the currently set target spectrum."""
        sid = self._view_model.target_id
        if sid is not None:
            self._view_model.analyze(
                sid,
                observer=self._observer_combo.currentText(),
                illuminant=self._illuminant_combo.currentText(),
            )
            # Plot chart
            spec = self._spectrum_ctrl.get_spectrum(sid)
            if spec is not None:
                summary = self._view_model._target_summary
                name = summary.name if summary is not None else f"Spectrum {sid}"
                self._chart.clear()
                self._chart.plot_spectrum(spec, label=name)
        else:
            self._view_model.set_status("No spectrum selected. Use Spectrum page to select one.")

    def _reanalyze(self) -> None:
        """Re-run analysis when observer/illuminant changes."""
        sid = self._view_model.target_id
        if sid is not None:
            self._view_model.analyze(
                sid,
                observer=self._observer_combo.currentText(),
                illuminant=self._illuminant_combo.currentText(),
            )

    def _on_analysis_changed(self, result: dict) -> None:
        """Display analysis results including CCT, u'v', dominant wavelength."""
        self._last_result = result or {}
        xyz = self._last_result.get("xyz")
        xy = self._last_result.get("xy")
        if xyz is not None and xy is not None:
            lines = [f"<b>XYZ</b>: ({xyz.X:.3f}, {xyz.Y:.3f}, {xyz.Z:.3f})"]
            mode = self._display_mode.currentText()
            if "xy" in mode:
                lines.append(f"<b>xy</b>: ({xy.x:.3f}, {xy.y:.3f})")
            upv = self._last_result.get("uprime_vprime")
            if upv is not None and "u'v'" in mode:
                lines.append(f"<b>u'v'</b>: ({upv[0]:.3f}, {upv[1]:.3f})")
            cct = self._last_result.get("cct")
            if cct is not None:
                lines.append(f"<b>CCT</b>: {cct:.0f} K")
            dom_wl = self._last_result.get("dominant_wavelength")
            if dom_wl is not None:
                lines.append(f"<b>Dominant Wavelength</b>: {dom_wl:.0f} nm")
        else:
            lines = ["Analysis result unavailable."]
        self._result_text.setHtml("<br>".join(lines))

    def _on_compare_gamuts(self) -> None:
        """Compare two standard gamuts and show coverage / match."""
        target = self._target_gamut_combo.currentText()
        device = self._device_gamut_combo.currentText()
        result = self._view_model.compare_gamuts(target, device)
        if result is None:
            return
        coverage = result.get("coverage")
        match = result.get("match")
        self._gamut_result_label.setText(
            f"<b>{device}</b> vs <b>{target}</b>:<br>"
            f"Coverage: {coverage:.2f}%<br>"
            f"Match: {match:.2f}%"
        )

    def _on_spectrum_vs_gamut(self) -> None:
        """Check the selected spectrum against a target gamut."""
        gamut_name = self._spectrum_gamut_combo.currentText()
        result = self._view_model.spectrum_vs_gamut(gamut_name)
        if result is None:
            return
        inside = result.get("inside", False)
        match = result.get("match", 0.0)
        xy = result.get("xy")
        self._spectrum_gamut_label.setText(
            f"Spectrum xy: ({xy.x:.3f}, {xy.y:.3f})<br>"
            f"Inside <b>{gamut_name}</b>: {'Yes' if inside else 'No'}<br>"
            f"Match to white: {match:.2f}%"
        )

    def set_spectrum_id(self, spectrum_id: int) -> None:
        """Set the spectrum to analyze by id."""
        self._view_model.analyze(
            spectrum_id,
            observer=self._observer_combo.currentText(),
            illuminant=self._illuminant_combo.currentText(),
        )
        # Plot chart
        spec = self._spectrum_ctrl.get_spectrum(spectrum_id)
        if spec is not None:
            self._chart.clear()
            self._chart.plot_spectrum(spec, label=f"Spectrum {spectrum_id}")

    def _on_delta_e(self) -> None:
        """Compute Delta E between the target and the selected reference."""
        if self._delta_ref_combo.count() == 0:
            return
        reference_id = self._delta_ref_combo.currentData()
        method = self._delta_method_combo.currentText()
        value = self._view_model.delta_e(
            reference_id,
            method=method,
            observer=self._observer_combo.currentText(),
            illuminant=self._illuminant_combo.currentText(),
        )
        if value is None:
            return
        self._delta_result_label.setText(
            f"<b>{self._delta_ref_combo.currentText()}</b> vs target:<br>"
            f"Delta E ({method}): {value:.4f}"
        )
