"""ColorService orchestrates color-mixing and colorimetric reports."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from colorlab_pro.dto.color import XY, XYZ
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.color_calculator import (
    delta_e,
    delta_uv,
    luminance,
    mix_spectra,
    mix_xy,
    mix_xyz,
)
from colorlab_pro.repositories import spectrum_repository


class ColorService:
    """Service for spectrum mixing and colorimetric calculations."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Initialize with a factory that produces SQLAlchemy sessions.

        Args:
            session_factory: Callable returning a new ORM session.
        """
        self._session_factory = session_factory

    def mix_spectra(
        self,
        spectra: list[Spectrum],
        weights: list[float] | None = None,
    ) -> Spectrum:
        """Return the additive mixture of the provided spectra."""
        return mix_spectra(spectra, weights=weights)

    def mix_spectra_by_id(
        self,
        spectrum_ids: list[int],
        weights: list[float] | None = None,
    ) -> Spectrum:
        """Load spectra by id and return their additive mixture.

        Raises:
            ValueError: If any id cannot be resolved to a spectrum.
        """
        with self._session_factory() as session:
            spectra: list[Spectrum] = []
            for sid in spectrum_ids:
                spectrum = spectrum_repository.get_by_id(session, sid)
                if spectrum is None:
                    raise ValueError(f"Spectrum {sid} not found")
                spectra.append(spectrum)
        return mix_spectra(spectra, weights=weights)

    def mixed_xyz(self, spectra: list[Spectrum], weights: list[float] | None = None) -> XYZ:
        """Compute the XYZ of an additive mixture of spectra."""
        return mix_xyz(spectra, weights=weights)

    def mixed_xy(self, xy_list: list[XY], weights: list[float] | None = None) -> XY:
        """Compute the weighted centroid of chromaticities."""
        return mix_xy(xy_list, weights=weights)

    def luminance(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float:
        """Return the luminance (Y) of a spectrum."""
        return luminance(spectrum, observer=observer, illuminant=illuminant)

    def delta_uv_to_d65(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float:
        """Return the distance from the spectrum's chromaticity to the planckian locus."""
        _cct, duv = delta_uv(spectrum, observer=observer, illuminant=illuminant)
        return duv

    def delta_e(
        self,
        spectrum_a: Spectrum,
        spectrum_b: Spectrum,
        *,
        method: str = "CIE 2000",
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float:
        """Return the colour difference between two spectra."""
        return delta_e(
            spectrum_a,
            spectrum_b,
            method=method,
            observer=observer,
            illuminant=illuminant,
        )
