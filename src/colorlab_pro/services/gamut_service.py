"""GamutService orchestrates gamut coverage and match calculations."""

from __future__ import annotations

from colorlab_pro.dto.color import XY, Gamut
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.gamut_calculator import (
    area,
    build_gamut_from_primaries,
    contains,
    coverage,
    coverage_1976,
    match,
    match_1976,
    standard_gamuts,
)
from colorlab_pro.engines.gamut_calculator import (
    match_spectrum as _engine_match_spectrum,
)
from colorlab_pro.engines.spectrum_analyzer import xy


def _spectrum_to_xy(spectrum: Spectrum) -> XY:
    """Compute xy chromaticity for a spectrum."""
    return xy(spectrum)


class GamutService:
    """Service for gamut construction, coverage, and match analysis."""

    def build_from_primaries(
        self,
        red: Spectrum,
        green: Spectrum,
        blue: Spectrum,
        white: Spectrum | None = None,
        name: str = "custom",
    ) -> Gamut:
        """Build a Gamut DTO from measured primary spectra.

        Args:
            red: Red primary spectrum.
            green: Green primary spectrum.
            blue: Blue primary spectrum.
            white: Optional white spectrum. Defaults to D65 (0.3127, 0.3290).
            name: Gamut name.

        Returns:
            Gamut DTO with vertices in xy space.
        """
        red_xy = _spectrum_to_xy(red)
        green_xy = _spectrum_to_xy(green)
        blue_xy = _spectrum_to_xy(blue)
        white_xy = _spectrum_to_xy(white) if white is not None else XY(x=0.3127, y=0.3290)
        return build_gamut_from_primaries(name, red_xy, green_xy, blue_xy, white_xy)

    def standard_gamut(self, name: str) -> Gamut:
        """Return a built-in standard gamut by name."""
        return standard_gamuts(name)

    def list_standard_gamuts(self) -> list[str]:
        """Return the names of all supported standard gamuts."""
        return ["sRGB", "DCI-P3", "Adobe RGB", "NTSC", "BT2020"]

    def coverage(self, target_name: str, device: Gamut) -> float:
        """Compute target coverage by a device gamut.

        Args:
            target_name: Name of a standard target gamut.
            device: Measured or designed device gamut.

        Returns:
            Coverage percentage [0.0, 100.0].
        """
        target = standard_gamuts(target_name)
        return coverage(target, device)

    def match(self, target_name: str, device: Gamut) -> float:
        """Compute vertex-wise match between a target and a device gamut.

        Args:
            target_name: Name of a standard target gamut.
            device: Measured or designed device gamut.

        Returns:
            Match percentage [0.0, 100.0].
        """
        target = standard_gamuts(target_name)
        return match(target, device)

    def coverage_1976(self, target_name: str, device: Gamut) -> float:
        """Compute target coverage in CIE 1976 u'v' space."""
        target = standard_gamuts(target_name)
        return coverage_1976(target, device)

    def match_1976(self, target_name: str, device: Gamut) -> float:
        """Compute vertex-wise match in CIE 1976 u'v' space."""
        target = standard_gamuts(target_name)
        return match_1976(target, device)

    def area(self, gamut: Gamut) -> float:
        """Return the area of a gamut triangle in xy space."""
        return area(gamut)

    def contains(self, gamut: Gamut, point: XY) -> bool:
        """Check whether a chromaticity point lies inside a gamut triangle."""
        return contains(gamut, point)

    def match_spectrum(self, target_xy: XY, sample_xy: XY, saturation: float = 0.1) -> float:
        """Compute match of a single color (target vs sample) in xy space."""
        return _engine_match_spectrum(target_xy, sample_xy, saturation=saturation)
