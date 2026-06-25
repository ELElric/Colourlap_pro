"""Web-based Spectrum Library page."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog, QWidget

from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.engines.spectrum_analyzer import dominant_wavelength, uprime_vprime, xy
from colorlab_pro.ui.utils.clipboard_parser import parse_spectrum_from_text
from colorlab_pro.ui.webview_page import WebViewPage


def _sample_points(spectrum, step: int = 5) -> list[list[float]]:
    """Return a down-sampled list of [wavelength, value] for charting."""
    if spectrum is None or len(spectrum.wavelengths) == 0:
        return []
    return [
        [round(float(w), 1), round(float(v), 4)]
        for w, v in zip(spectrum.wavelengths[::step], spectrum.values[::step], strict=False)
    ]


class SpectrumPageBackend(QObject):
    """Backend exposed to the Spectrum page JavaScript via QWebChannel."""

    def __init__(self, controller: SpectrumController, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

    @Slot(result=str)
    def get_spectra(self) -> str:
        """Return the spectrum list as JSON."""
        try:
            summaries = self._controller.list_spectra()
            spectra = []
            for s in summaries:
                full_spec = self._controller.get_spectrum(s.id)
                if full_spec is not None:
                    try:
                        xy_val = xy(full_spec)
                        uv_val = uprime_vprime(full_spec)
                        dom = dominant_wavelength(full_spec)
                        xy_str = f"{xy_val.x:.4f}, {xy_val.y:.4f}"
                        uv_str = f"{uv_val[0]:.4f}, {uv_val[1]:.4f}"
                        dom_str = str(round(dom)) if dom is not None else "-"
                        purity_str = "-"
                    except Exception:
                        xy_str = uv_str = dom_str = purity_str = "-"
                else:
                    xy_str = uv_str = dom_str = purity_str = "-"

                spectra.append(
                    {
                        "id": s.id,
                        "name": s.name,
                        "category": s.category or "",
                        "channel": s.channel or "",
                        "peak_nm": s.peak_wavelength if s.peak_wavelength is not None else "-",
                        "fwhm_nm": s.fwhm if s.fwhm is not None else "-",
                        "thickness_um": (
                            f"{s.thickness_um:.2f}" if s.thickness_um is not None else "-"
                        ),
                        "xy": xy_str,
                        "uv": uv_str,
                        "dominant_nm": dom_str,
                        "purity": purity_str,
                        "data": _sample_points(full_spec),
                    }
                )
            return json.dumps(spectra)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})

    @Slot(str, result=str)
    def delete_spectra(self, ids_json: str) -> str:
        """Delete selected spectra. Returns {deleted: int} or {error}."""
        try:
            ids = json.loads(ids_json)
            deleted = 0
            for sid in ids:
                if self._controller.delete_spectrum(sid):
                    deleted += 1
            return json.dumps({"deleted": deleted})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})

    @Slot(result=str)
    def import_spectra(self) -> str:
        """Open a file dialog and import CSV/XLSX/TXT spectra."""
        parent = self.parent()
        path_str, _ = QFileDialog.getOpenFileName(
            parent,
            "Import Spectrum",
            "",
            "Spectrum Files (*.csv *.xlsx *.txt);;All Files (*)",
        )
        if not path_str:
            return json.dumps({"ids": [], "cancelled": True})
        path = Path(path_str)
        try:
            suffix = path.suffix.lower()
            if suffix == ".xlsx":
                result = self._controller.import_xlsx_file(path)
            else:
                result = self._controller.import_csv_file(path)
            ids = result if isinstance(result, list) else ([result] if result else [])
            return json.dumps({"ids": [i for i in ids if i is not None]})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})

    @Slot(str, result=str)
    def export_selected(self, ids_json: str) -> str:
        """Export selected spectra to a user-chosen directory."""
        parent = self.parent()
        ids = json.loads(ids_json)
        if not ids:
            return json.dumps({"error": "No spectra selected"})
        dir_str = QFileDialog.getExistingDirectory(parent, "Export Spectra", "")
        if not dir_str:
            return json.dumps({"cancelled": True})
        from colorlab_pro.exporters.csv_exporter import export_spectrum

        out_dir = Path(dir_str)
        exported = 0
        for sid in ids:
            spec = self._controller.get_spectrum(sid)
            if spec is None:
                continue
            name = spec.meta.get("name", f"spectrum_{sid}") if spec.meta else f"spectrum_{sid}"
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            export_spectrum(spec, out_dir / f"{safe_name}.csv")
            exported += 1
        return json.dumps({"path": str(out_dir), "exported": exported})

    @Slot(str, result=str)
    def paste_spectrum(self, payload: str) -> str:
        """Parse clipboard text and save as a new spectrum."""
        try:
            data = json.loads(payload)
            text = data.get("text", "")
            name = data.get("name", "Pasted Spectrum")
            spectrum = parse_spectrum_from_text(text)
            if spectrum.meta is None:
                spectrum.meta = {}
            spectrum.meta["name"] = name
            spectrum.meta["category"] = spectrum.meta.get("category", "Pasted")
            sid = self._controller.import_spectrum(spectrum, name=name, category="Pasted")
            if sid is None:
                return json.dumps({"error": "Failed to import pasted spectrum"})
            return json.dumps({"id": sid})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})


class SpectrumPage(WebViewPage):
    """Spectrum Library workspace page rendered as HTML."""

    def __init__(
        self,
        controller: SpectrumController,
        page_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._page_index = page_index
        self.initialize()

    def html_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "web" / "spectrum_page.html"

    def create_backend(self) -> QObject:
        return SpectrumPageBackend(self._controller, self)

    def page_script(self) -> str:
        return """
        setLoading(true);
        if (typeof qt === 'undefined' || !qt.webChannelTransport) {
            console.error('QWebChannel transport not available');
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            channel.objects.backend.get_spectra(function(json) {
                var data = JSON.parse(json);
                if (data.error) {
                    console.error('Backend error:', data.error);
                    setLoading(false);
                    return;
                }
                renderSpectra(data);
                logStatus('Loaded ' + data.length + ' spectra');
            });
        });
        """

    def _on_page_about_to_show(self, index: int) -> None:
        """Refresh data when the page becomes visible."""
        if index == self._page_index:
            self.run_javascript("""
                setLoading(true);
                if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        channel.objects.backend.get_spectra(function(json) {
                            var data = JSON.parse(json);
                            if (data.error) {
                                console.error('Refresh error:', data.error);
                                setLoading(false);
                                return;
                            }
                            renderSpectra(data);
                        });
                    });
                } else {
                    setLoading(false);
                }
            """)

    def connect_auto_refresh(self, window: QWidget) -> None:
        window.page_about_to_show.connect(self._on_page_about_to_show)

    def refresh(self) -> None:
        """Public API: force a data refresh."""
        self._on_page_about_to_show(self._page_index)
