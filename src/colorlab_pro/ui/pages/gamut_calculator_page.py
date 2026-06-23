"""Web-based Gamut Calculator page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QWidget

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.ui.webview_page import WebViewPage


class GamutPageBackend(QObject):
    """Backend exposed to the Gamut Calculator page JavaScript."""

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_controller = spectrum_controller
        self._color_controller = color_controller

    @Slot(result=str)
    def get_initial_data(self) -> str:
        """Return spectra list and placeholder gamut results as JSON."""
        import json

        try:
            summaries = self._spectrum_controller.list_spectra()
            spectra = [
                {"id": s.id, "name": s.name, "category": s.category or "", "channel": s.channel or ""}
                for s in summaries
            ]

            results = [
                {"standard": std, "coverage_1931": 0.0, "match_1931": 0.0, "coverage_1976": 0.0, "match_1976": 0.0}
                for std in ["sRGB", "NTSC", "DCI-P3", "BT2020"]
            ]

            return json.dumps({"spectra": spectra, "results": results})
        except Exception as exc:  # noqa: BLE001
            import json
            import traceback

            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})


class GamutCalculatorPage(WebViewPage):
    """Gamut Calculator workspace page rendered as HTML."""

    white_point_calculated = Signal(object, object, object)

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        page_index: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_controller = spectrum_controller
        self._color_controller = color_controller
        self._page_index = page_index
        self.initialize()

    def html_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "web" / "gamut_calculator_page.html"

    def create_backend(self) -> QObject:
        return GamutPageBackend(self._spectrum_controller, self._color_controller, self)

    def page_script(self) -> str:
        return """
        if (typeof qt === 'undefined' || !qt.webChannelTransport) {
            console.error('QWebChannel transport not available');
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            channel.objects.backend.get_initial_data(function(json) {
                var data = JSON.parse(json);
                if (data.error) {
                    console.error('Backend error:', data.error);
                    return;
                }
                if (typeof populateSelectors === 'function') populateSelectors(data.spectra);
                if (typeof renderResults === 'function') renderResults(data.results);
                if (typeof logStatus === 'function') logStatus('Loaded gamut data');
            });
        });
        """

    def connect_auto_refresh(self, window: QWidget) -> None:
        window.page_about_to_show.connect(self._on_page_about_to_show)

    def _on_page_about_to_show(self, index: int) -> None:
        if index == self._page_index:
            self.run_javascript("""
                if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                    new QWebChannel(qt.webChannelTransport, function(channel) {
                        channel.objects.backend.get_initial_data(function(json) {
                            var data = JSON.parse(json);
                            if (typeof populateSelectors === 'function') populateSelectors(data.spectra);
                            if (typeof renderResults === 'function') renderResults(data.results);
                        });
                    });
                }
            """)

    def refresh_spectrum_list(self) -> None:
        """Public API: refresh the spectrum selectors."""
        self._on_page_about_to_show(self._page_index)
