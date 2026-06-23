"""SpectrumViewModel — data model for the Spectrum page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from colorlab_pro.controllers.spectrum_controller import SpectrumController, SpectrumSummary
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.viewmodels.base import ViewModel


class SpectrumViewModel(ViewModel):
    """ViewModel for spectrum list, import, and analysis state."""

    # Emitted when the spectrum list has been refreshed.
    spectrum_list_changed = Signal()

    # Emitted when a spectrum is selected (carries SpectrumSummary or None).
    selection_changed = Signal(object)

    # Emitted when analysis results are ready.
    analysis_updated = Signal(dict)

    def __init__(
        self,
        controller: SpectrumController,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with a SpectrumController reference.

        Args:
            controller: The spectrum controller for data operations.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._spectra: list[SpectrumSummary] = []
        self._selected: SpectrumSummary | None = None
        self._analysis: dict | None = None
        self._analysis_worker = None
        self._analysis_request_id: int | None = None

        # Connect controller signals
        self._controller.spectra_updated.connect(self.refresh)
        # analysis_ready is now handled via run_in_background on_result callback
        self._controller.error_occurred.connect(self.set_error)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def spectra(self) -> list[SpectrumSummary]:
        """Return the cached spectrum list."""
        return self._spectra

    @property
    def selected_spectrum(self) -> SpectrumSummary | None:
        """Return the currently selected spectrum summary."""
        return self._selected

    @property
    def analysis(self) -> dict | None:
        """Return the latest analysis result."""
        return self._analysis

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Reload the spectrum list from the controller."""
        self._spectra = self._controller.list_spectra()
        self.spectrum_list_changed.emit()
        self.data_changed.emit()

    def select_spectrum(self, spectrum_id: int | None) -> None:
        """Select a spectrum by id."""
        if spectrum_id is None:
            self._selected = None
        else:
            self._selected = next(
                (s for s in self._spectra if s.id == spectrum_id),
                None,
            )
        self.selection_changed.emit(self._selected)

    def import_spectrum(
        self, spectrum: Spectrum, *, name: str | None = None, channel: str | None = None
    ) -> int | None:
        """Import a spectrum via the controller."""
        sid = self._controller.import_spectrum(spectrum, name=name, channel=channel)
        if sid is not None:
            self.set_status(f"Spectrum imported (id={sid}).")
        return sid

    def import_file(
        self,
        path,
        *,
        name: str | None = None,
        channel: str | None = None,
        category: str | None = None,
    ) -> list[int] | int | None:
        """Import spectrum(s) from a file (CSV, Excel, or TXT).

        Detects the file type from the extension and delegates to the
        appropriate controller method.
        """
        from pathlib import Path

        suffix = Path(path).suffix.lower()
        if suffix == ".csv":
            return self._controller.import_csv_file(
                path, name=name, channel=channel, category=category
            )
        if suffix == ".xlsx":
            return self._controller.import_xlsx_file(
                path, name=name, channel=channel, category=category
            )
        if suffix == ".txt":
            return self._controller.import_txt_file(
                path, name=name, channel=channel, category=category
            )
        self.set_error(f"Unsupported file type: {suffix}")
        return None

    def rename_spectrum(self, spectrum_id: int, new_name: str) -> bool:
        """Rename a spectrum via the controller."""
        result = self._controller.rename_spectrum(spectrum_id, new_name)
        if result:
            self.refresh()
        return result

    def duplicate_spectrum(self, spectrum_id: int) -> int | None:
        """Duplicate a spectrum via the controller."""
        sid = self._controller.duplicate_spectrum(spectrum_id)
        if sid is not None:
            self.refresh()
        return sid

    def delete_spectrum(self, spectrum_id: int) -> bool:
        """Delete a spectrum via the controller."""
        result = self._controller.delete_spectrum(spectrum_id)
        if result and self._selected is not None and self._selected.id == spectrum_id:
            self._selected = None
            self.selection_changed.emit(None)
        return result

    def analyze(
        self,
        spectrum_id: int,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "D65",
    ) -> None:
        """Analyze a spectrum asynchronously via the controller.

        Results are delivered through the ``analysis_updated`` signal.
        This method returns immediately and does not block the UI thread.
        """
        from colorlab_pro.ui.workers import run_in_background

        # Track the latest requested spectrum_id to discard stale results
        self._analysis_request_id = spectrum_id
        self._analysis_worker = run_in_background(
            fn=lambda: self._controller.analyze_spectrum(
                spectrum_id, observer=observer, illuminant=illuminant
            ),
            on_result=self._on_analysis_async_done,
            on_error=self._on_analysis_async_error,
        )

    def _on_analysis_async_done(self, result: object) -> None:
        """Handle async analysis result (called on UI thread via signal)."""
        if result is not None and isinstance(result, dict):
            # Only accept the result if it matches the latest request
            result_sid = result.get("spectrum_id")
            if result_sid is not None and result_sid != self._analysis_request_id:
                return  # Stale result from a previous request, discard
            self._analysis = result
            self.analysis_updated.emit(result)

    def _on_analysis_async_error(self, error_msg: str) -> None:
        """Handle async analysis error (called on UI thread via signal)."""
        self.set_error(error_msg)

    def update_channel(self, spectrum_id: int, channel: str) -> bool:
        """Update a spectrum's channel label."""
        return self._controller.update_channel(spectrum_id, channel)

    def preprocess(
        self,
        spectrum_id: int,
        *,
        normalize_mode: str | None = None,
        interpolate_step: int | None = None,
        interpolate_method: str = "cubic",
        fill_gaps: bool = False,
        fill_value: float = 0.0,
        min_gap_nm: float = 5.0,
        suffix: str = "",
    ) -> int | None:
        """Apply preprocessing to a spectrum."""
        return self._controller.preprocess_spectrum(
            spectrum_id,
            normalize_mode=normalize_mode,
            interpolate_step=interpolate_step,
            interpolate_method=interpolate_method,
            fill_gaps=fill_gaps,
            fill_value=fill_value,
            min_gap_nm=min_gap_nm,
            suffix=suffix,
        )

    def _on_analysis_ready(self, result: dict) -> None:
        """Handle analysis results from the controller."""
        self._analysis = result
        self.analysis_updated.emit(result)
