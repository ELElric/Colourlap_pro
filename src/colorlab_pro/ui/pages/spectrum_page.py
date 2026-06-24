"""Web-based Spectrum Library page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QWidget

from colorlab_pro.controllers.spectrum_controller import SpectrumController
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
                        "data": _sample_points(full_spec),
                    }
                )
            import json

            return json.dumps(spectra)
        except Exception as exc:  # noqa: BLE001
            import json
            import traceback

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
        if (typeof qt === 'undefined' || !qt.webChannelTransport) {
            console.error('QWebChannel transport not available');
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            channel.objects.backend.get_spectra(function(json) {
                var data = JSON.parse(json);
                if (data.error) {
                    console.error('Backend error:', data.error);
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
                if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        channel.objects.backend.get_spectra(function(json) {
                            renderSpectra(JSON.parse(json));
                        });
                    });
                }
            """)

    def connect_auto_refresh(self, window: QWidget) -> None:
        window.page_about_to_show.connect(self._on_page_about_to_show)

    def refresh(self) -> None:
        """Public API: force a data refresh."""
        self._on_page_about_to_show(self._page_index)
