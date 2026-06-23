"""ReportPage — workspace page for exporting reports."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.exporters.csv_exporter import export_spectrum as export_csv_spectrum
from colorlab_pro.exporters.json_exporter import export_spectrum as export_json_spectrum
from colorlab_pro.exporters.xlsx_exporter import export_spectrum as export_xlsx_spectrum


class ReportPage(QWidget):
    """Workspace page for exporting data and reports."""

    def __init__(
        self,
        main_controller: MainController,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize with a MainController reference.

        Args:
            main_controller: For export path dialogs and service access.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._main = main_controller
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the page layout."""
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Export</h3>"))
        header.addStretch()

        self._csv_btn = QPushButton("Export CSV")
        self._xlsx_btn = QPushButton("Export Excel")
        self._json_btn = QPushButton("Export JSON")
        self._pdf_btn = QPushButton("Export PDF")
        self._pdf_btn.setToolTip("PDF report export is planned for a future release.")
        header.addWidget(self._csv_btn)
        header.addWidget(self._xlsx_btn)
        header.addWidget(self._json_btn)
        header.addWidget(self._pdf_btn)
        layout.addLayout(header)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setPlaceholderText("Export log will appear here.")
        layout.addWidget(self._log_text)

        self._csv_btn.clicked.connect(self._on_export_csv)
        self._xlsx_btn.clicked.connect(self._on_export_xlsx)
        self._json_btn.clicked.connect(self._on_export_json)
        self._pdf_btn.clicked.connect(self._on_export_pdf)

    def _get_current_spectra(self):
        """Load all spectra in the current project."""
        if self._main.spectrum_service is None or self._main.current_project_id is None:
            return []
        return self._main.spectrum_service.list_spectra(self._main.current_project_id)

    def _on_export_csv(self) -> None:
        """Export current project spectra as CSV."""
        path = self._main.prompt_export_path("Export CSV", "CSV (*.csv)")
        if path is None:
            return
        spectra = self._get_current_spectra()
        if not spectra:
            self._log_text.append("No spectra to export. Select a project first.")
            return
        try:
            for i, spec in enumerate(spectra):
                out = path.parent / f"{path.stem}_{i}.csv" if len(spectra) > 1 else path
                export_csv_spectrum(spec, out)
            self._log_text.append(f"CSV export complete: {len(spectra)} spectrum(ies) saved.")
        except Exception as exc:  # noqa: BLE001
            self._log_text.append(f"CSV export failed: {exc}")

    def _on_export_xlsx(self) -> None:
        """Export current project spectra as Excel."""
        path = self._main.prompt_export_path("Export Excel", "Excel (*.xlsx)")
        if path is None:
            return
        spectra = self._get_current_spectra()
        if not spectra:
            self._log_text.append("No spectra to export. Select a project first.")
            return
        try:
            for i, spec in enumerate(spectra):
                out = path.parent / f"{path.stem}_{i}.xlsx" if len(spectra) > 1 else path
                export_xlsx_spectrum(spec, out)
            self._log_text.append(f"Excel export complete: {len(spectra)} spectrum(ies) saved.")
        except Exception as exc:  # noqa: BLE001
            self._log_text.append(f"Excel export failed: {exc}")

    def _on_export_json(self) -> None:
        """Export current project spectra as JSON."""
        path = self._main.prompt_export_path("Export JSON", "JSON (*.json)")
        if path is None:
            return
        spectra = self._get_current_spectra()
        if not spectra:
            self._log_text.append("No spectra to export. Select a project first.")
            return
        try:
            for i, spec in enumerate(spectra):
                out = path.parent / f"{path.stem}_{i}.json" if len(spectra) > 1 else path
                export_json_spectrum(spec, out)
            self._log_text.append(f"JSON export complete: {len(spectra)} spectrum(ies) saved.")
        except Exception as exc:  # noqa: BLE001
            self._log_text.append(f"JSON export failed: {exc}")

    def _on_export_pdf(self) -> None:
        """Placeholder for PDF report export."""
        path = self._main.prompt_export_path("Export PDF", "PDF (*.pdf)")
        if path is None:
            return
        self._log_text.append(
            f"PDF report export is not implemented in V1.1. Selected path: {path}"
        )
