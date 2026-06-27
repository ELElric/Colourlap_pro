"""SpectrumController — manages spectrum CRUD and analysis.

Mediates between the Spectrum page UI and SpectrumService.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.importers.csv_importer import import_csv
from colorlab_pro.importers.xlsx_importer import import_xlsx


@dataclass(frozen=True)
class SpectrumSummary:
    """Lightweight DTO for UI spectrum lists."""

    id: int
    name: str
    channel: str | None
    source: str
    wavelength_min: float | None
    wavelength_max: float | None
    point_count: int | None
    category: str | None = None
    peak_wavelength: float | None = None
    created_at: str | None = None
    thickness_um: float | None = None
    thickness_missing: bool = False
    fwhm: float | None = None
    xy_x: float | None = None
    xy_y: float | None = None
    uv_u: float | None = None
    uv_v: float | None = None
    dominant_wavelength: float | None = None
    purity: float | None = None

    @property
    def xy_str(self) -> str | None:
        if self.xy_x is None or self.xy_y is None:
            return None
        return f"{self.xy_x:.4f}, {self.xy_y:.4f}"

    @property
    def uv_str(self) -> str | None:
        if self.uv_u is None or self.uv_v is None:
            return None
        return f"{self.uv_u:.4f}, {self.uv_v:.4f}"

    @property
    def dominant_wavelength_str(self) -> str | None:
        if self.dominant_wavelength is None:
            return None
        return str(round(self.dominant_wavelength))

    @property
    def purity_str(self) -> str | None:
        if self.purity is None:
            return None
        return f"{self.purity * 100:.1f}"


class SpectrumController(QObject):
    """Controller for spectrum lifecycle and analysis operations."""

    # Emitted when the spectrum list changes.
    spectra_updated = Signal()

    # Emitted when a single spectrum is imported (carries its id).
    spectrum_imported = Signal(int)

    # Emitted when a spectrum is deleted (carries its id).
    spectrum_deleted = Signal(int)

    # Emitted with analysis results dict.
    analysis_ready = Signal(dict)

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
    # Internal helper
    # ------------------------------------------------------------------ #

    def _service(self):
        """Return the SpectrumService from MainController."""
        if self._main.spectrum_service is None:
            raise RuntimeError("SpectrumService not available.")
        return self._main.spectrum_service

    def _require_project(self) -> int:
        """Return the current project id or raise."""
        pid = self._main.current_project_id
        if pid is None:
            raise RuntimeError("No project selected.")
        return pid

    # ------------------------------------------------------------------ #
    # Import / CRUD
    # ------------------------------------------------------------------ #

    def import_spectrum(
        self,
        spectrum: Spectrum,
        *,
        name: str | None = None,
        channel: str | None = None,
        category: str | None = None,
        skip_dedup: bool = False,
    ) -> int | None:
        """Import a Spectrum DTO into the current project."""
        try:
            project_id = self._require_project()
            sid = self._service().import_spectrum(
                project_id,
                spectrum,
                name=name,
                channel=channel,
                category=category,
                skip_dedup=skip_dedup,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to import spectrum: {exc}")
            return None

        self.spectra_updated.emit()
        self.spectrum_imported.emit(sid)
        return sid

    def import_csv_file(
        self,
        path: Path,
        *,
        name: str | None = None,
        channel: str | None = None,
        category: str | None = None,
    ) -> list[int] | int | None:
        """Import spectrum(s) from a CSV file."""
        try:
            result = import_csv(path, default_category=category)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to load CSV: {exc}")
            return None

        # Single spectrum
        if isinstance(result, Spectrum):
            return self.import_spectrum(
                result, name=name or path.stem, channel=channel, category=category
            )

        # Multiple spectra
        if isinstance(result, list):
            ids: list[int] = []
            for spectrum in result:
                spec_name = spectrum.meta.get("name", None) if spectrum.meta else None
                sid = self.import_spectrum(
                    spectrum,
                    name=spec_name or f"{path.stem}_{len(ids) + 1}",
                    channel=channel,
                    category=category,
                )
                if sid is not None:
                    ids.append(sid)
            return ids

        return None

    def import_xlsx_file(
        self,
        path: Path,
        *,
        name: str | None = None,
        channel: str | None = None,
        category: str | None = None,
    ) -> list[int] | int | None:
        """Import spectrum(s) from an Excel file."""
        try:
            result = import_xlsx(path, default_category=category)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to load Excel: {exc}")
            return None

        if isinstance(result, Spectrum):
            return self.import_spectrum(
                result, name=name or path.stem, channel=channel, category=category
            )

        if isinstance(result, list):
            ids: list[int] = []
            for spectrum in result:
                spec_name = spectrum.meta.get("name", None) if spectrum.meta else None
                sid = self.import_spectrum(
                    spectrum,
                    name=spec_name or f"{path.stem}_{len(ids) + 1}",
                    channel=channel,
                    category=category,
                )
                if sid is not None:
                    ids.append(sid)
            return ids

        return None

    def import_txt_file(
        self,
        path: Path,
        *,
        name: str | None = None,
        channel: str | None = None,
        category: str | None = None,
    ) -> list[int] | int | None:
        """Import spectrum(s) from a TXT file.

        TXT files use the same tabular format as CSV (the csv_importer
        handles both).
        """
        return self.import_csv_file(path, name=name, channel=channel, category=category)

    def rename_spectrum(self, spectrum_id: int, new_name: str) -> bool:
        """Rename a spectrum. Returns True on success."""
        try:
            from colorlab_pro.database.models import Spectrum as SpectrumORM

            with self._main.session_factory() as session:
                orm = session.get(SpectrumORM, spectrum_id)
                if orm is None:
                    self.error_occurred.emit(f"Spectrum {spectrum_id} not found.")
                    return False
                orm.name = new_name
                session.commit()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to rename spectrum: {exc}")
            return False

        self.spectra_updated.emit()
        return True

    def duplicate_spectrum(self, spectrum_id: int) -> int | None:
        """Duplicate a spectrum. Returns the new spectrum id."""
        spec = self.get_spectrum(spectrum_id)
        if spec is None:
            return None
        return self.import_spectrum(
            spec,
            name=f"{spec.meta.get('name', 'Spectrum')} (copy)" if spec.meta else "Spectrum (copy)",
            channel=spec.meta.get("channel") if spec.meta else None,
            category=spec.meta.get("category") if spec.meta else None,
            skip_dedup=True,
        )

    def _resolve_category(self, orm) -> str | None:
        """Resolve the spectrum category from the ORM row."""
        category = orm.category
        if not category:
            from colorlab_pro.engines.spectrum_normalizer import category_from_channel
            category = category_from_channel(orm.channel)
        return category

    def _compute_fwhm_and_peak(self, orm) -> tuple[float | None, float | None]:
        """Compute FWHM and peak wavelength from spectrum points if not pre-computed."""
        peak_wl = orm.peak_wavelength
        fwhm = orm.fwhm
        if (peak_wl is not None and fwhm is not None) or not orm.points:
            return peak_wl, fwhm

        import numpy as np
        wavelengths = np.array([p.wavelength for p in orm.points], dtype=np.float64)
        values = np.array([p.value for p in orm.points], dtype=np.float64)
        if values.size == 0:
            return peak_wl, fwhm

        if peak_wl is None:
            peak_wl = float(wavelengths[int(np.argmax(values))])

        if fwhm is None and values.size >= 3:
            peak_val = float(np.max(values))
            if peak_val > 0:
                half_max = peak_val / 2.0
                peak_idx = int(np.argmax(values))
                left_wl: float | None = None
                for i in range(peak_idx - 1, -1, -1):
                    if values[i] < half_max:
                        if i + 1 < values.size:
                            frac = (half_max - values[i]) / (values[i + 1] - values[i])
                            left_wl = wavelengths[i] + frac * (wavelengths[i + 1] - wavelengths[i])
                        break
                right_wl: float | None = None
                for i in range(peak_idx + 1, values.size):
                    if values[i] < half_max:
                        if i - 1 >= 0:
                            frac = (half_max - values[i - 1]) / (values[i] - values[i - 1])
                            right_wl = wavelengths[i - 1] + frac * (wavelengths[i] - wavelengths[i - 1])
                        break
                if left_wl is not None and right_wl is not None:
                    fwhm = float(right_wl - left_wl)

        return peak_wl, fwhm

    def _parse_thickness(self, orm) -> tuple[float | None, bool]:
        """Extract thickness info from meta_json."""
        thickness: float | None = None
        thickness_missing = False
        if orm.meta_json:
            import json
            try:
                meta = json.loads(orm.meta_json)
                thickness = meta.get("thickness_um")
                thickness_missing = meta.get("thickness_missing", False)
            except (json.JSONDecodeError, TypeError):
                pass
        return thickness, thickness_missing

    def list_spectra(self) -> list[SpectrumSummary]:
        """Return all spectra in the current project."""
        pid = self._main.current_project_id
        if pid is None:
            return []
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from colorlab_pro.database.models import Spectrum as SpectrumORM

            with self._main.session_factory() as session:
                stmt = (
                    select(SpectrumORM)
                    .options(selectinload(SpectrumORM.points))
                    .where(SpectrumORM.project_id == pid)
                    .order_by(SpectrumORM.created_at)
                )
                orms = session.scalars(stmt).all()
                result: list[SpectrumSummary] = []
                for orm in orms:
                    category = self._resolve_category(orm)
                    peak_wl, fwhm = self._compute_fwhm_and_peak(orm)
                    thickness, thickness_missing = self._parse_thickness(orm)

                    created_at_str = None
                    if orm.created_at is not None:
                        created_at_str = orm.created_at.strftime("%Y-%m-%d %H:%M")

                    result.append(
                        SpectrumSummary(
                            id=int(orm.id),
                            name=orm.name or "Untitled",
                            channel=orm.channel,
                            source=orm.source or "import",
                            wavelength_min=orm.wavelength_min,
                            wavelength_max=orm.wavelength_max,
                            point_count=orm.point_count,
                            category=category,
                            peak_wavelength=peak_wl,
                            created_at=created_at_str,
                            thickness_um=thickness,
                            thickness_missing=thickness_missing,
                            fwhm=fwhm,
                            xy_x=orm.xy_x,
                            xy_y=orm.xy_y,
                            uv_u=orm.uv_u,
                            uv_v=orm.uv_v,
                            dominant_wavelength=orm.dominant_wavelength,
                            purity=orm.purity,
                        )
                    )
                return result
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to list spectra: {exc}")
            return []

    def get_spectrum(self, spectrum_id: int) -> Spectrum | None:
        """Load a full Spectrum DTO by id."""
        try:
            return self._service().get_spectrum(spectrum_id)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to get spectrum: {exc}")
            return None

    def delete_spectrum(self, spectrum_id: int) -> bool:
        """Delete a spectrum. Returns True if it existed."""
        try:
            result = self._service().delete_spectrum(spectrum_id)
            if not result:
                self.error_occurred.emit(f"Spectrum {spectrum_id} not found.")
                return False
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to delete spectrum: {exc}")
            return False

        self.spectra_updated.emit()
        self.spectrum_deleted.emit(spectrum_id)
        return True

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #

    def analyze_spectrum(
        self,
        spectrum_id: int,
        *,
        observer: str = "CIE 1931 2 Degree Standard Observer",
        illuminant: str = "E",
    ) -> dict | None:
        """Analyze a spectrum and return colorimetric metrics.

        Emits ``analysis_ready`` with the result dict on success.
        """
        try:
            result = self._service().analyze(spectrum_id, observer=observer, illuminant=illuminant)
            if result is None:
                self.error_occurred.emit(f"Spectrum {spectrum_id} not found.")
                return None
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Analysis failed: {exc}")
            return None

        # Tag the result with the spectrum_id for stale-result detection
        result["spectrum_id"] = spectrum_id
        self.analysis_ready.emit(result)
        return result

    def detect_channel(self, spectrum: Spectrum) -> str:
        """Detect the channel type of a spectrum."""
        return self._service().detect_channel(spectrum)

    def update_channel(self, spectrum_id: int, channel: str) -> bool:
        """Update the channel label of a spectrum."""
        try:
            result = self._service().update_channel(spectrum_id, channel)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to update channel: {exc}")
            return False
        if result:
            self.spectra_updated.emit()
        return result

    def update_category(self, spectrum_id: int, category: str) -> bool:
        """Update the category label of a spectrum."""
        try:
            from colorlab_pro.database.models import Spectrum as SpectrumORM

            with self._main.session_factory() as session:
                orm = session.get(SpectrumORM, spectrum_id)
                if orm is None:
                    return False
                orm.category = category
                session.commit()
            self.spectra_updated.emit()
            return True
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to update category: {exc}")
            return False

    def update_thickness(self, spectrum_id: int, thickness: float | None) -> bool:
        """Update the thickness_um value in meta_json."""
        try:
            import json

            from colorlab_pro.database.models import Spectrum as SpectrumORM

            with self._main.session_factory() as session:
                orm = session.get(SpectrumORM, spectrum_id)
                if orm is None:
                    return False
                meta: dict = {}
                if orm.meta_json:
                    try:
                        meta = json.loads(orm.meta_json)
                    except (json.JSONDecodeError, TypeError):
                        pass
                if thickness is None:
                    meta.pop("thickness_um", None)
                    meta["thickness_missing"] = True
                else:
                    meta["thickness_um"] = thickness
                    meta.pop("thickness_missing", None)
                orm.meta_json = json.dumps(meta, ensure_ascii=False, sort_keys=True)
                session.commit()
            self.spectra_updated.emit()
            return True
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Failed to update thickness: {exc}")
            return False

    def preprocess_spectrum(
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
        """Apply preprocessing to a spectrum and return the new spectrum id."""
        try:
            new_id = self._service().preprocess(
                spectrum_id,
                normalize_mode=normalize_mode,
                interpolate_step=interpolate_step,
                interpolate_method=interpolate_method,
                fill_gaps=fill_gaps,
                fill_value=fill_value,
                min_gap_nm=min_gap_nm,
                suffix=suffix,
            )
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Preprocessing failed: {exc}")
            return None
        if new_id is not None:
            self.spectra_updated.emit()
            self.spectrum_imported.emit(new_id)
        return new_id
