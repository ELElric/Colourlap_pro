"""ColorController — manages color mixing, gamut, and analysis operations.

Mediates between the Mix/Analyze/Gamut pages and ColorService / GamutService.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.dto.color import XY, XYZ, Gamut
from colorlab_pro.dto.spectrum import Spectrum


@dataclass(frozen=True)
class MixResult:
    """Result of a spectrum mixing operation."""

    spectrum: Spectrum
    xyz: XYZ
    xy: XY


@dataclass(frozen=True)
class GamutResult:
    """Result of a gamut analysis operation."""

    name: str
    area: float
    coverage: float | None
    match: float | None


class ColorController(QObject):
    """Controller for color mixing, gamut, and analysis operations."""

    # Emitted when a mix operation completes.
    mix_ready = Signal(object)

    # Emitted when a gamut analysis completes.
    gamut_ready = Signal(object)

    # Emitted on operation errors.
    error_occurred = Signal(str)

    def __init__(
        self,
        main_controller: MainController,
        parent: QObject | None = None,
    ) -> None:
        """Initialize with a reference to MainController.

        Args:
            main_controller: The application-level coordinator.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._main = main_controller

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _color_service(self):
        """Return the ColorService from MainController."""
        if self._main.color_service is None:
            raise RuntimeError("ColorService not available.")
        return self._main.color_service

    def _gamut_service(self):
        """Return the GamutService from MainController."""
        if self._main.gamut_service is None:
            raise RuntimeError("GamutService not available.")
        return self._main.gamut_service

    # ------------------------------------------------------------------ #
    # Mixing
    # ------------------------------------------------------------------ #

    def mix_spectra(
        self,
        spectra: list[Spectrum],
        weights: list[float] | None = None,
    ) -> MixResult | None:
        """Mix a list of spectra and return the result.

        Args:
            spectra: List of Spectrum DTOs to mix.
            weights: Optional weight list.

        Returns:
            MixResult with spectrum, xyz, and xy, or None on error.
        """
        try:
            mixed = self._color_service().mix_spectra(spectra, weights=weights)
            xyz = self._color_service().mixed_xyz(spectra, weights=weights)
            from colorlab_pro.engines.spectrum_analyzer import xy as calc_xy

            xy = calc_xy(mixed)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Mix failed: {exc}")
            return None

        result = MixResult(spectrum=mixed, xyz=xyz, xy=xy)
        self.mix_ready.emit(result)
        return result

    def mix_spectra_by_id(
        self,
        spectrum_ids: list[int],
        weights: list[float] | None = None,
    ) -> MixResult | None:
        """Load spectra by id and mix them.

        Args:
            spectrum_ids: List of spectrum ids.
            weights: Optional weight list.

        Returns:
            MixResult or None on error.
        """
        # Need to load spectra for xyz calculation
        spectra = []
        for sid in spectrum_ids:
            spec = self._main.spectrum_service.get_spectrum(sid)
            if spec is None:
                self.error_occurred.emit(f"Spectrum {sid} not found.")
                return None
            spectra.append(spec)

        return self.mix_spectra(spectra, weights=weights)

    # ------------------------------------------------------------------ #
    # Gamut
    # ------------------------------------------------------------------ #

    def build_gamut_from_primaries(
        self,
        red: Spectrum,
        green: Spectrum,
        blue: Spectrum,
        white: Spectrum | None = None,
        name: str = "custom",
    ) -> GamutResult | None:
        """Build a gamut from primary spectra and compute metrics.

        Args:
            red: Red primary spectrum.
            green: Green primary spectrum.
            blue: Blue primary spectrum.
            white: Optional white spectrum.
            name: Gamut name.

        Returns:
            GamutResult or None on error.
        """
        try:
            gamut = self._gamut_service().build_from_primaries(
                red, green, blue, white=white, name=name
            )
            area = self._gamut_service().area(gamut)
            coverage = self._gamut_service().coverage("sRGB", gamut)
            match = self._gamut_service().match("sRGB", gamut)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Gamut build failed: {exc}")
            return None

        result = GamutResult(
            name=gamut.name,
            area=area,
            coverage=coverage,
            match=match,
        )
        self.gamut_ready.emit(result)
        return result

    def compare_to_standard(self, gamut_name: str, device_name: str = "custom") -> dict | None:
        """Compare a standard gamut to a device gamut.

        Args:
            gamut_name: Name of the standard gamut (e.g. "sRGB").
            device_name: Name of the device gamut.

        Returns:
            Dict with coverage and match percentages, or None.
        """
        try:
            self._gamut_service().standard_gamut(gamut_name)
            device = self._gamut_service().standard_gamut(device_name)
            coverage = self._gamut_service().coverage(gamut_name, device)
            match = self._gamut_service().match(gamut_name, device)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Gamut comparison failed: {exc}")
            return None

        result = {
            "standard": gamut_name,
            "device": device_name,
            "coverage": coverage,
            "match": match,
        }
        self.gamut_ready.emit(result)
        return result

    def list_standard_gamuts(self) -> list[str]:
        """Return the list of supported standard gamut names."""
        return self._gamut_service().list_standard_gamuts()

    def project_gamut_coverage(
        self,
        standard_name: str,
        spectra: list[Spectrum],
    ) -> dict | None:
        """Build a gamut from the first three project spectra and compare it.

        Args:
            standard_name: Name of the standard target gamut.
            spectra: Project spectra; the first three are treated as R, G, B.

        Returns:
            Dict with ``standard``, ``coverage``, ``match``, ``area``.
        """
        if len(spectra) < 3:
            self.error_occurred.emit("Need at least 3 spectra to build a gamut.")
            return None
        try:
            device = self._gamut_service().build_from_primaries(
                spectra[0], spectra[1], spectra[2], name="project"
            )
            coverage = self._gamut_service().coverage(standard_name, device)
            match = self._gamut_service().match(standard_name, device)
            area = self._gamut_service().area(device)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Gamut coverage failed: {exc}")
            return None

        return {
            "standard": standard_name,
            "coverage": coverage,
            "match": match,
            "area": area,
        }

    def spectrum_vs_gamut(
        self,
        spectrum: Spectrum,
        gamut_name: str,
    ) -> dict | None:
        """Check how a single spectrum relates to a standard gamut.

        Computes whether the spectrum chromaticity lies inside the gamut
        triangle and a match score to the gamut white point.

        Args:
            spectrum: The spectrum to evaluate.
            gamut_name: Name of the standard target gamut.

        Returns:
            Dict with keys ``gamut``, ``inside``, ``match``, ``xy``.
        """
        try:
            gamut = self._gamut_service().standard_gamut(gamut_name)
            spectrum_xy = self.xy(spectrum)
            white_xy = XY(x=gamut.white[0], y=gamut.white[1])
            inside = self._gamut_service().contains(gamut, spectrum_xy)
            match = self._gamut_service().match_spectrum(white_xy, spectrum_xy)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Spectrum vs gamut failed: {exc}")
            return None

        return {
            "gamut": gamut_name,
            "inside": inside,
            "match": match,
            "xy": spectrum_xy,
        }

    # ------------------------------------------------------------------ #
    # Analysis helpers
    # ------------------------------------------------------------------ #

    def luminance(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float:
        """Return the luminance (Y) of a spectrum."""
        return self._color_service().luminance(spectrum, observer=observer, illuminant=illuminant)

    def delta_uv_to_d65(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float:
        """Return the distance from the spectrum's chromaticity to D65."""
        return self._color_service().delta_uv_to_d65(
            spectrum, observer=observer, illuminant=illuminant
        )

    def delta_e(
        self,
        spectrum_a: Spectrum,
        spectrum_b: Spectrum,
        *,
        method: str = "CIE 2000",
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float | None:
        """Compute the colour difference between two spectra.

        Returns:
            Delta E value or None on error.
        """
        try:
            return self._color_service().delta_e(
                spectrum_a,
                spectrum_b,
                method=method,
                observer=observer,
                illuminant=illuminant,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Delta E failed: {exc}")
            return None

    # ------------------------------------------------------------------ #
    # Spectrum analysis (delegated to SpectrumService)
    # ------------------------------------------------------------------ #

    def _spectrum_service(self):
        """Return the SpectrumService from MainController."""
        if self._main.spectrum_service is None:
            raise RuntimeError("SpectrumService not available.")
        return self._main.spectrum_service

    def xy(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> XY:
        """Compute xy chromaticity for a spectrum."""
        return self._spectrum_service().xy(spectrum, observer=observer, illuminant=illuminant)

    def cct_mccamy(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float:
        """Compute correlated color temperature using McCamy's formula."""
        return self._spectrum_service().cct_mccamy(
            spectrum, observer=observer, illuminant=illuminant
        )

    def uprime_vprime(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> tuple[float, float]:
        """Compute CIE 1976 u'v' chromaticity for a spectrum."""
        return self._spectrum_service().uprime_vprime(
            spectrum, observer=observer, illuminant=illuminant
        )

    def mix_xy(self, xy_list: list[XY], weights: list[float] | None = None) -> XY:
        """Compute the weighted centroid of chromaticities."""
        return self._color_service().mixed_xy(xy_list, weights=weights)

    def build_gamut_from_primaries_direct(
        self,
        name: str,
        red: XY,
        green: XY,
        blue: XY,
        white: XY,
    ) -> Gamut:
        """Build a Gamut DTO from xy coordinates (no spectrum conversion)."""
        from colorlab_pro.engines.gamut_calculator import build_gamut_from_primaries

        return build_gamut_from_primaries(name, red, green, blue, white)

    def coverage(self, target_name: str, device: Gamut) -> float:
        """Compute target coverage by a device gamut."""
        return self._gamut_service().coverage(target_name, device)

    def match(self, target_name: str, device: Gamut) -> float:
        """Compute vertex-wise match between a target and a device gamut."""
        return self._gamut_service().match(target_name, device)

    def coverage_1976(self, target_name: str, device: Gamut) -> float:
        """Compute target coverage in CIE 1976 u'v' space."""
        return self._gamut_service().coverage_1976(target_name, device)

    def match_1976(self, target_name: str, device: Gamut) -> float:
        """Compute vertex-wise match in CIE 1976 u'v' space."""
        return self._gamut_service().match_1976(target_name, device)

    def standard_gamut(self, name: str) -> Gamut:
        """Return a built-in standard gamut by name."""
        return self._gamut_service().standard_gamut(name)
