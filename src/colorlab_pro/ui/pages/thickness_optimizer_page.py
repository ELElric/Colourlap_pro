"""Web-based Thickness Optimizer page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QWidget

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.ui.webview_page import WebViewPage


class OptimizerPageBackend(QObject):
    """Backend exposed to the Thickness Optimizer page JavaScript."""

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
        """Return spectra list and simulated optimization results as JSON."""
        import json

        try:
            summaries = self._spectrum_controller.list_spectra()
            spectra = [
                {"id": s.id, "name": s.name, "category": s.category or "", "channel": s.channel or ""}
                for s in summaries
            ]

            results = [
                {"rank": i + 1, "thickness_r": 1.0 + i * 0.1, "thickness_g": 1.2 + i * 0.1, "thickness_b": 1.4 + i * 0.1, "coverage": 85.0 - i * 2.5}
                for i in range(5)
            ]

            return json.dumps({"spectra": spectra, "results": results, "best": results[0]})
        except Exception as exc:  # noqa: BLE001
            import traceback

            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})


class ThicknessOptimizerPage(WebViewPage):
    """Thickness Optimizer workspace page rendered as HTML."""

    optimization_finished = Signal(list)
    progress_update = Signal(str)

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        optimization_controller: OptimizationController | None = None,
        page_index: int = 3,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_controller = spectrum_controller
        self._color_controller = color_controller
        self._optimization_controller = optimization_controller
        self._page_index = page_index
        self.initialize()

    def html_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "web" / "thickness_optimizer_page.html"

    def create_backend(self) -> QObject:
        return OptimizerPageBackend(self._spectrum_controller, self._color_controller, self)

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
                if (typeof renderResults === 'function') renderResults(data.results, data.best);
                if (typeof logStatus === 'function') logStatus('Loaded optimizer data');
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
                            if (typeof renderResults === 'function') renderResults(data.results, data.best);
                        });
                    });
                }
            """)

    def refresh_spectrum_list(self) -> None:
        """Public API: refresh the spectrum selectors."""
        self._on_page_about_to_show(self._page_index)
