"""AnalyzeViewModel — data model for the Analyze page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.spectrum_controller import SpectrumController, SpectrumSummary
from colorlab_pro.dto.color_constants import DELTA_E_METHODS, ILLUMINANT_CHOICES, OBSERVER_CHOICES
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.viewmodels.base import ViewModel


class AnalyzeViewModel(ViewModel):
    """ViewModel for the Analyze page.

    Tracks the target spectrum and exposes analysis results, including
    optional observer / illuminant selection and Delta E comparisons.
    """

    # Emitted when analysis results change.
    analysis_changed = Signal(dict)

    # Emitted when the target spectrum changes.
    target_changed = Signal(object)

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with controller references.

        Args:
            spectrum_controller: For loading spectrum data.
            color_controller: For colorimetric computations.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._spectrum_ctrl = spectrum_controller
        self._color_ctrl = color_controller
        self._target: Spectrum | None = None
        self._target_summary: SpectrumSummary | None = None
        self._analysis: dict | None = None
        self._analysis_worker = None

        self._color_ctrl.error_occurred.connect(self.set_error)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def target(self) -> Spectrum | None:
        """Return the currently analyzed spectrum."""
        return self._target

    @property
    def target_id(self) -> int | None:
        """Return the id of the currently analyzed spectrum, or None."""
        if self._target_summary is not None:
            return self._target_summary.id
        return None

    @property
    def analysis(self) -> dict | None:
        """Return the latest analysis result."""
        return self._analysis

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def set_target(self, spectrum: Spectrum) -> None:
        """Set the target spectrum directly (used by tests / UI cross-links)."""
        self._target = spectrum
        self._target_summary = None
        self.target_changed.emit(self._target)

    def analyze(
        self,
        spectrum_id: int,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> None:
        """Analyze the given spectrum asynchronously and emit results.

        Results are delivered through the ``analysis_changed`` signal.
        This method returns immediately and does not block the UI thread.

        Args:
            spectrum_id: Id of the spectrum to analyze.
            observer: Standard observer name.
            illuminant: Illuminant name.
        """
        from colorlab_pro.ui.workers import run_in_background

        self.set_status("Analyzing spectrum...")

        # Capture controllers for background use (thread-safe: no Qt widget access)
        spectrum_ctrl = self._spectrum_ctrl
        color_ctrl = self._color_ctrl

        def _do_analyze() -> dict | None:
            spectrum = spectrum_ctrl.get_spectrum(spectrum_id)
            if spectrum is None:
                return None

            result = spectrum_ctrl.analyze_spectrum(
                spectrum_id, observer=observer, illuminant=illuminant
            )
            if result is None:
                return None

            try:
                result["luminance"] = color_ctrl.luminance(
                    spectrum, observer=observer, illuminant=illuminant
                )
            except Exception:  # noqa: BLE001
                pass

            return {"spectrum": spectrum, "result": result, "spectrum_id": spectrum_id}

        def _on_done(data: object) -> None:
            if data is None:
                self.set_error(f"Spectrum {spectrum_id} not found or analysis failed.")
                return
            assert isinstance(data, dict)
            spectrum: Spectrum = data["spectrum"]
            result: dict = data["result"]
            self._target = spectrum
            self._target_summary = self._find_summary(spectrum_id)
            self.target_changed.emit(self._target)
            self._analysis = result
            self.analysis_changed.emit(result)
            self.set_status("Analysis complete.")

        def _on_error(msg: str) -> None:
            self.set_error(f"Analysis failed: {msg}")

        self._analysis_worker = run_in_background(
            fn=_do_analyze,
            on_result=_on_done,
            on_error=_on_error,
        )

    def delta_e(
        self,
        reference_id: int,
        *,
        method: str = "CIE 2000",
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float | None:
        """Compute Delta E between the target spectrum and a reference.

        Args:
            reference_id: Id of the reference spectrum.
            method: Delta E method.
            observer: Standard observer name.
            illuminant: Illuminant name.

        Returns:
            Delta E value or None on error.
        """
        if self._target is None:
            self.set_error("No target spectrum selected.")
            return None
        reference = self._spectrum_ctrl.get_spectrum(reference_id)
        if reference is None:
            self.set_error(f"Reference spectrum {reference_id} not found.")
            return None
        return self._color_ctrl.delta_e(
            self._target,
            reference,
            method=method,
            observer=observer,
            illuminant=illuminant,
        )

    def standard_gamuts(self) -> list[str]:
        """Return the list of supported standard gamut names."""
        return self._color_ctrl.list_standard_gamuts()

    def compare_gamuts(self, target: str, device: str) -> dict | None:
        """Compare two standard gamuts and return coverage / match."""
        self.set_status("Computing gamut coverage / match...")
        return self._color_ctrl.compare_to_standard(target, device)

    def spectrum_vs_gamut(self, gamut_name: str) -> dict | None:
        """Check whether the current target spectrum lies inside a gamut."""
        if self._target is None:
            self.set_error("No spectrum selected.")
            return None
        return self._color_ctrl.spectrum_vs_gamut(self._target, gamut_name)

    def observers(self) -> list[str]:
        """Return supported standard observer names."""
        return OBSERVER_CHOICES

    def illuminants(self) -> list[str]:
        """Return supported illuminant names."""
        return ILLUMINANT_CHOICES

    def delta_e_methods(self) -> list[str]:
        """Return supported Delta E method names."""
        return DELTA_E_METHODS

    def _find_summary(self, spectrum_id: int) -> SpectrumSummary | None:
        """Find the SpectrumSummary for the given id from the controller."""
        for summary in self._spectrum_ctrl.list_spectra():
            if summary.id == spectrum_id:
                return summary
        return None
