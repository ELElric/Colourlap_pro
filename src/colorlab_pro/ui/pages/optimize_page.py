"""OptimizePage — workspace page for optimization operations."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.ui.viewmodels.optimize_viewmodel import OptimizeViewModel


class OptimizePage(QWidget):
    """Workspace page for white-point and thickness optimization."""

    def __init__(
        self,
        controller: OptimizationController,
        color_controller: ColorController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize with an OptimizationController.

        Args:
            controller: The optimization controller.
            color_controller: Optional color controller for gamut coverage.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._view_model = OptimizeViewModel(controller, color_controller, parent=self)
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        """Construct the page layout."""
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Optimize</h3>"))
        header.addStretch()
        self._wp_btn = QPushButton("Optimize White Point")
        self._th_btn = QPushButton("Optimize Thickness")
        header.addWidget(self._wp_btn)
        header.addWidget(self._th_btn)
        layout.addLayout(header)

        # Parameters form
        form = QFormLayout()

        self._target_x_edit = QLineEdit("0.3127")
        self._target_x_edit.setPlaceholderText("Target x (e.g. 0.3127)")
        self._target_y_edit = QLineEdit("0.3290")
        self._target_y_edit.setPlaceholderText("Target y (e.g. 0.3290)")

        target_row = QWidget()
        target_layout = QHBoxLayout(target_row)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(QLabel("x:"))
        target_layout.addWidget(self._target_x_edit)
        target_layout.addWidget(QLabel("y:"))
        target_layout.addWidget(self._target_y_edit)
        form.addRow("Target xy", target_row)

        gamut_row = QWidget()
        gamut_layout = QHBoxLayout(gamut_row)
        gamut_layout.setContentsMargins(0, 0, 0, 0)
        self._gamut_combo = QComboBox()
        self._gamut_combo.addItems(["sRGB", "DCI-P3", "Adobe RGB", "NTSC"])
        gamut_layout.addWidget(self._gamut_combo)
        self._gamut_btn = QPushButton("Coverage / Match")
        gamut_layout.addWidget(self._gamut_btn)
        form.addRow("Standard Gamut", gamut_row)

        layout.addLayout(form)

        self._gamut_result_label = QLabel("Select a standard gamut and click Coverage / Match.")
        self._gamut_result_label.setWordWrap(True)
        layout.addWidget(self._gamut_result_label)

        # Save result
        save_row = QWidget()
        save_layout = QHBoxLayout(save_row)
        save_layout.setContentsMargins(0, 0, 0, 0)
        self._save_name_edit = QLineEdit("Thickness Result")
        self._save_name_edit.setPlaceholderText("Result name")
        self._save_btn = QPushButton("Save Result")
        self._save_btn.setEnabled(False)
        save_layout.addWidget(self._save_name_edit)
        save_layout.addWidget(self._save_btn)
        layout.addWidget(save_row)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setPlaceholderText(
            "Set target xy and click an optimize button.\n"
            "Uses the current project's spectra as primaries."
        )
        layout.addWidget(self._result_text)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def _wire_signals(self) -> None:
        """Connect UI signals."""
        self._wp_btn.clicked.connect(self._on_wp)
        self._th_btn.clicked.connect(self._on_th)
        self._gamut_btn.clicked.connect(self._on_gamut_coverage)
        self._save_btn.clicked.connect(self._on_save_result)
        self._view_model.white_point_changed.connect(self._on_wp_result)
        self._view_model.thickness_changed.connect(self._on_th_result)
        self._view_model.error_occurred.connect(
            lambda msg: self._status_label.setText(f"Error: {msg}")
        )
        self._view_model.status_changed.connect(lambda msg: self._status_label.setText(msg))

    def _read_target_xy(self):
        """Read target xy from the input fields with validation."""
        from colorlab_pro.dto.color import XY

        try:
            x = float(self._target_x_edit.text())
            y = float(self._target_y_edit.text())
        except ValueError:
            self._view_model.set_error("Invalid target xy values — must be numbers.")
            return None
        # Validate CIE xy range
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            self._view_model.set_error("Target xy must be in range [0, 1].")
            return None
        if x + y > 1.0:
            self._view_model.set_error(
                f"Invalid chromaticity: x + y = {x + y:.4f} > 1.0. "
                "Check your target white point values."
            )
            return None
        return XY(x=x, y=y)

    def _get_project_spectra(self):
        """Load all spectra from the current project as primaries."""
        main = self._view_model._controller._main
        if main.spectrum_service is None or main.current_project_id is None:
            self._view_model.set_error("No project selected.")
            return []
        spectra = main.spectrum_service.list_spectra(main.current_project_id)
        if len(spectra) < 2:
            self._view_model.set_error("Need at least 2 spectra in the project.")
            return []
        return spectra

    def _on_wp(self) -> None:
        """Trigger white-point optimization in background thread."""
        target = self._read_target_xy()
        if target is None:
            return
        spectra = self._get_project_spectra()
        if not spectra:
            return
        self._wp_btn.setEnabled(False)
        self._status_label.setText("Optimizing white point...")
        from colorlab_pro.ui.workers import run_in_background

        run_in_background(
            lambda: self._view_model.optimize_white_point(spectra, target),
            on_result=lambda r: self._wp_btn.setEnabled(True),
            on_error=lambda e: (
                self._status_label.setText(f"Error: {e}"),
                self._wp_btn.setEnabled(True),
            ),
        )

    def _on_th(self) -> None:
        """Trigger thickness optimization in background thread."""
        target = self._read_target_xy()
        if target is None:
            return
        spectra = self._get_project_spectra()
        if len(spectra) < 3:
            self._view_model.set_error(
                "Thickness optimization needs at least 3 spectra (source + 2 absorbers)."
            )
            return
        source = spectra[0]
        absorbers = spectra[1:]
        self._th_btn.setEnabled(False)
        self._status_label.setText("Optimizing thickness...")
        from colorlab_pro.ui.workers import run_in_background

        run_in_background(
            lambda: self._view_model.optimize_thickness(target, source, absorbers),
            on_result=lambda r: self._th_btn.setEnabled(True),
            on_error=lambda e: (
                self._status_label.setText(f"Error: {e}"),
                self._th_btn.setEnabled(True),
            ),
        )

    def _on_gamut_coverage(self) -> None:
        """Compute coverage/match using the first three project spectra."""
        spectra = self._get_project_spectra()
        if len(spectra) < 3:
            self._view_model.set_error("Need at least 3 spectra to build a gamut.")
            return
        standard = self._gamut_combo.currentText()
        result = self._view_model.project_gamut_coverage(standard, spectra)
        if result is None:
            return
        self._gamut_result_label.setText(
            f"Project gamut vs <b>{result['standard']}</b>:<br>"
            f"Coverage: {result['coverage']:.2f}%<br>"
            f"Match: {result['match']:.2f}%<br>"
            f"Area: {result['area']:.5f}"
        )

    def _on_save_result(self) -> None:
        """Save the last thickness optimization result."""
        name = self._save_name_edit.text().strip()
        if not name:
            self._view_model.set_error("Please enter a result name.")
            return
        opt_id = self._view_model.save_thickness_result(name)
        if opt_id is not None:
            self._status_label.setText(f"Saved optimization as '{name}' (id={opt_id}).")

    def _on_wp_result(self, result) -> None:
        """Display white-point results."""
        if result is None:
            return
        self._result_text.setHtml(
            f"<b>White Point Result</b><br>"
            f"Weights: {[f'{w:.4f}' for w in result.weights]}<br>"
            f"Achieved xy: ({result.achieved_xy.x:.4f}, {result.achieved_xy.y:.4f})<br>"
            f"Delta xy: {result.delta_xy:.6f}<br>"
            f"Nearest standard: {result.nearest_white_point}"
        )

    def _on_th_result(self, result) -> None:
        """Display thickness results and enable save."""
        if result is None:
            return
        self._save_btn.setEnabled(True)
        self._result_text.setHtml(
            f"<b>Thickness Result</b><br>"
            f"Thicknesses (um): {[f'{t:.3f}' for t in result.thicknesses_um]}<br>"
            f"Achieved xy: ({result.achieved_xy.x:.4f}, {result.achieved_xy.y:.4f})<br>"
            f"Delta xy: {result.delta_xy:.6f}<br>"
            f"Converged: {result.converged} ({result.iterations} iterations)"
        )
