"""SpectrumService orchestrates spectrum-related business use cases."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from colorlab_pro.dto.color import XY
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.spectrum_analyzer import (
    _get_illuminant_xy,
    cct_mccamy,
    dominant_wavelength,
    uprime_vprime,
    xy,
    xyz,
)
from colorlab_pro.engines.spectrum_normalizer import (
    auto_fill_gaps,
    category_from_channel,
    detect_category,
    detect_channel,
    interpolate,
    normalize,
)
from colorlab_pro.repositories import project_repository, spectrum_repository


class SpectrumService:
    """Service for importing, loading, analyzing, and deleting spectra."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """Initialize with a factory that produces SQLAlchemy sessions.

        Args:
            session_factory: Callable returning a new ORM session.
        """
        self._session_factory = session_factory

    def import_spectrum(
        self,
        project_id: int,
        spectrum: Spectrum,
        *,
        name: str | None = None,
        source: str = "import",
        channel: str | None = None,
        category: str | None = None,
        skip_dedup: bool = False,
    ) -> int:
        """Import a spectrum into a project and return its id.

        If the spectrum data already exists in the project (dedup), returns
        the existing id without creating a duplicate. Use skip_dedup=True
        to force creating a new entry (e.g. for explicit duplicates).

        Note: The original spectrum is stored as-is to preserve data fidelity.
        Alignment to the standard 380-780 nm range is applied only during
        analysis, not at import time.
        """
        with self._session_factory() as session:
            if project_repository.get_by_id(session, project_id) is None:
                raise ValueError(f"Project {project_id} does not exist")

            # Store the original spectrum directly (no forced alignment).
            # Alignment to 380-780 nm is applied on-demand during analysis.
            stored = spectrum

            # Prefer user-provided channel; only auto-detect when not given.
            if channel is None:
                channel = detect_channel(stored)

            # Use category from meta (set by importer) if not explicitly provided
            if category is None:
                meta_category = stored.meta.get("category") if stored.meta else None
                if meta_category:
                    category = meta_category

            if category is None:
                detected_category = detect_category(stored)
            else:
                detected_category = category
            if category is None and channel is not None:
                detected_category = category_from_channel(channel)

            # Check for duplicate (unless skip_dedup)
            if not skip_dedup:
                existing_id = spectrum_repository.find_duplicate(
                    session,
                    project_id,
                    stored.wavelengths,
                    stored.values,
                    category=detected_category,
                )
                if existing_id is not None:
                    # Update channel/category on the matched record
                    spectrum_repository.update_spectrum_fields(
                        session,
                        existing_id,
                        channel=channel,
                        category=detected_category,
                    )
                    session.commit()
                    return existing_id

            spectrum_id = spectrum_repository.save(
                session,
                stored,
                project_id,
                name=name,
                source=source,
                channel=channel,
                category=detected_category,
            )
            session.commit()
            return spectrum_id

    def get_spectrum(self, spectrum_id: int) -> Spectrum | None:
        """Load a Spectrum DTO by id."""
        with self._session_factory() as session:
            return spectrum_repository.get_by_id(session, spectrum_id)

    def list_spectra(self, project_id: int) -> list[Spectrum]:
        """Return all spectra belonging to a project."""
        with self._session_factory() as session:
            return spectrum_repository.list_by_project(session, project_id)

    def delete_spectrum(self, spectrum_id: int) -> bool:
        """Delete a spectrum. Returns True if it existed."""
        with self._session_factory() as session:
            result = spectrum_repository.delete(session, spectrum_id)
            session.commit()
            return result

    def detect_channel(self, spectrum: Spectrum) -> str:
        """Detect the channel type of a spectrum."""
        return detect_channel(spectrum)

    def update_channel(self, spectrum_id: int, channel: str) -> bool:
        """Update the channel label of a stored spectrum."""
        with self._session_factory() as session:
            from colorlab_pro.database.models import Spectrum as SpectrumORM

            orm = session.get(SpectrumORM, spectrum_id)
            if orm is None:
                return False
            orm.channel = channel
            session.commit()
            return True

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
        """Apply preprocessing to a stored spectrum and save as a new spectrum.

        Args:
            spectrum_id: Source spectrum id.
            normalize_mode: "peak", "area", or None.
            interpolate_step: Target step in nm, or None to skip.
            interpolate_method: "cubic" or "pchip".
            fill_gaps: Whether to auto-fill NaN gaps.
            fill_value: Value for edge gaps.
            min_gap_nm: Maximum gap size to auto-fill.
            suffix: Name suffix for the new spectrum.

        Returns:
            New spectrum id, or None if source not found.
        """
        with self._session_factory() as session:
            from colorlab_pro.database.models import Spectrum as SpectrumORM

            orm = session.get(SpectrumORM, spectrum_id)
            if orm is None:
                return None
            spectrum = spectrum_repository._dto_from_orm(orm)

            result = spectrum
            if fill_gaps:
                result = auto_fill_gaps(result, fill_value=fill_value, min_gap_nm=min_gap_nm)
            if normalize_mode is not None:
                result = normalize(result, mode=normalize_mode)
            if interpolate_step is not None:
                result = interpolate(result, step=interpolate_step, method=interpolate_method)

            base_name = orm.name or "Spectrum"
            new_name = f"{base_name}{suffix}"
            channel = orm.channel
            category = orm.category
            new_id = spectrum_repository.save(
                session,
                result,
                orm.project_id,
                name=new_name,
                source="preprocessed",
                channel=channel,
                category=category,
            )
            session.commit()
            return int(new_id)

    def xy(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> XY:
        """Compute xy chromaticity for a spectrum."""
        from colorlab_pro.dto.color import XY

        result = xy(spectrum, observer=observer, illuminant=illuminant)
        return XY(x=result.x, y=result.y)

    def cct_mccamy(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> float:
        """Compute correlated color temperature using McCamy's formula."""
        return cct_mccamy(spectrum, observer=observer, illuminant=illuminant)

    def uprime_vprime(
        self,
        spectrum: Spectrum,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> tuple[float, float]:
        """Compute CIE 1976 u'v' chromaticity for a spectrum."""
        return uprime_vprime(spectrum, observer=observer, illuminant=illuminant)

    def analyze(
        self,
        spectrum_id: int,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> dict[str, object] | None:
        """Analyze a stored spectrum and return colorimetric metrics.

        Returns a dictionary with keys:
        - ``xyz``: XYZ tristimulus
        - ``xy``: xy chromaticity
        - ``uprime_vprime``: (u', v') tuple
        - ``cct``: correlated color temperature in Kelvin
        - ``dominant_wavelength``: dominant wavelength in nm, or None
        - ``purity``: excitation purity, or None
        - ``observer``: observer name used
        - ``illuminant``: illuminant name used

        Returns None if the spectrum does not exist.
        """
        with self._session_factory() as session:
            spectrum = spectrum_repository.get_by_id(session, spectrum_id)
            if spectrum is None:
                return None

            xy_val = xy(spectrum, observer=observer, illuminant=illuminant)
            dom_wl = dominant_wavelength(
                spectrum, observer=observer, illuminant=illuminant
            )

            # Compute excitation purity in-line (avoids redundant locus
            # computation in the UI thread).
            purity = self._compute_purity(xy_val, dom_wl, observer, illuminant)

            return {
                "xyz": xyz(spectrum, observer=observer, illuminant=illuminant),
                "xy": xy_val,
                "uprime_vprime": uprime_vprime(spectrum, observer=observer, illuminant=illuminant),
                "cct": cct_mccamy(spectrum, observer=observer, illuminant=illuminant),
                "dominant_wavelength": dom_wl,
                "purity": purity,
                "observer": observer,
                "illuminant": illuminant,
            }

    @staticmethod
    def _compute_purity(
        xy_val: XY,
        dom_wl: float | None,
        observer: str,
        illuminant: str,
    ) -> float | None:
        """Compute excitation purity from xy and dominant wavelength."""
        if xy_val is None or dom_wl is None:
            return None
        try:
            import numpy as np

            white = _get_illuminant_xy(illuminant, observer=observer)
            wavelengths = np.arange(380.0, 781.0, 1.0, dtype=np.float64)
            v = np.zeros_like(wavelengths)
            idx = int(dom_wl - 380.0)
            if 0 <= idx < v.size:
                v[idx] = 1.0
            s = Spectrum(wavelengths=wavelengths, values=v, unit="a.u.")
            locus_pt = xy(s, observer=observer, illuminant=illuminant)

            sample_vec = np.array([xy_val.x - white.x, xy_val.y - white.y])
            locus_vec = np.array([locus_pt.x - white.x, locus_pt.y - white.y])
            locus_norm = np.linalg.norm(locus_vec)
            if locus_norm < 1e-12:
                return None
            purity = float(np.linalg.norm(sample_vec) / locus_norm)
            return max(0.0, min(1.0, purity))
        except Exception:  # noqa: BLE001
            return None
