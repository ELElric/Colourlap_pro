"""MixViewModel — data model for the Mix page."""

from __future__ import annotations

from PySide6.QtCore import Signal

from colorlab_pro.controllers.color_controller import ColorController, MixResult
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.viewmodels.base import ViewModel


class MixViewModel(ViewModel):
    """ViewModel for spectrum mixing state."""

    # Emitted when the mix result is ready.
    mix_result_changed = Signal(object)

    # Emitted when the selected spectra list changes.
    selection_changed = Signal(list)

    def __init__(
        self,
        controller: ColorController,
        parent: object | None = None,
    ) -> None:
        """Initialize with a ColorController reference.

        Args:
            controller: The color controller for mix operations.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._selected_spectra: list[Spectrum] = []
        self._weights: list[float] = []
        self._mix_result: MixResult | None = None

        self._controller.mix_ready.connect(self._on_mix_ready)
        self._controller.error_occurred.connect(self.set_error)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def selected_spectra(self) -> list[Spectrum]:
        """Return the list of spectra selected for mixing."""
        return self._selected_spectra

    @property
    def weights(self) -> list[float]:
        """Return the current mixing weights."""
        return self._weights

    @property
    def mix_result(self) -> MixResult | None:
        """Return the latest mix result."""
        return self._mix_result

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def add_spectrum(self, spectrum: Spectrum) -> None:
        """Add a spectrum to the mix list."""
        self._selected_spectra.append(spectrum)
        self._weights.append(1.0)
        self.selection_changed.emit(self._selected_spectra)

    def remove_spectrum(self, index: int) -> None:
        """Remove a spectrum from the mix list by index."""
        if 0 <= index < len(self._selected_spectra):
            self._selected_spectra.pop(index)
            if index < len(self._weights):
                self._weights.pop(index)
            self.selection_changed.emit(self._selected_spectra)

    def clear_spectra(self) -> None:
        """Clear all spectra from the mix list."""
        self._selected_spectra.clear()
        self._weights.clear()
        self._mix_result = None
        self.selection_changed.emit(self._selected_spectra)
        self.mix_result_changed.emit(None)

    def set_weight(self, index: int, value: float) -> None:
        """Set the mixing weight for a spectrum by index."""
        if 0 <= index < len(self._weights):
            self._weights[index] = float(value)

    def mix(self, weights: list[float] | None = None) -> MixResult | None:
        """Execute the mix operation."""
        if not self._selected_spectra:
            self.set_error("No spectra selected for mixing.")
            return None
        self.set_status("Mixing spectra...")
        effective_weights = weights
        if effective_weights is None and len(self._weights) == len(self._selected_spectra):
            effective_weights = self._weights
        return self._controller.mix_spectra(self._selected_spectra, weights=effective_weights)

    def _on_mix_ready(self, result: MixResult) -> None:
        """Handle mix results from the controller."""
        self._mix_result = result
        self.mix_result_changed.emit(result)
        self.set_status("Mix complete.")
