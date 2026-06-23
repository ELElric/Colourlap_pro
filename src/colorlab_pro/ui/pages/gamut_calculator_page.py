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

    @Slot(str, str, str, result=str)
    def calculate_gamut(self, red_id: str, green_id: str, blue_id: str) -> str:
        """Calculate gamut coverage/match for the selected RGB spectra."""
        import json
        import traceback

        try:
            ids = [int(red_id), int(green_id), int(blue_id)]
            specs = [self._spectrum_controller.get_spectrum(sid) for sid in ids]
            gs = self._color_controller._gamut_service()
            device = gs.build_from_primaries(
                specs[0], specs[1], specs[2], name="Device"
            )

            primaries = [
                {"ch": "R", "x": round(device.red[0], 4), "y": round(device.red[1], 4)},
                {"ch": "G", "x": round(device.green[0], 4), "y": round(device.green[1], 4)},
                {"ch": "B", "x": round(device.blue[0], 4), "y": round(device.blue[1], 4)},
            ]

            results = []
            for std in ["sRGB", "NTSC", "DCI-P3", "BT2020"]:
                try:
                    cov = gs.coverage(std, device)
                    match = gs.match(std, device)
                    cov_1976 = gs.coverage_1976(std, device)
                    match_1976 = gs.match_1976(std, device)
                except Exception:  # noqa: BLE001
                    cov = match = cov_1976 = match_1976 = 0.0
                results.append(
                    {
                        "standard": std,
                        "coverage_1931": round(cov, 1),
                        "match_1931": round(match, 1),
                        "coverage_1976": round(cov_1976, 1),
                        "match_1976": round(match_1976, 1),
                    }
                )

            return json.dumps({"primaries": primaries, "results": results})
        except Exception as exc:  # noqa: BLE001
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
        return (
            "try {"
            "  new QWebChannel(qt.webChannelTransport, function(channel) {"
            "    channel.objects.backend.get_initial_data(function(json) {"
            "      var data = JSON.parse(json);"
            "      if (data.error) { logStatus('Backend error: ' + data.error); return; }"
            "      populateSelectors(data.spectra);"
            "      renderResults(data.results);"
            "      logStatus('Loaded gamut data');"
            "    });"
            "  });"
            "} catch (e) { logStatus('JS error: ' + e.message); }"
        )

    def connect_auto_refresh(self, window: QWidget) -> None:
        window.page_about_to_show.connect(self._on_page_about_to_show)

    def _on_page_about_to_show(self, index: int) -> None:
        if index == self._page_index:
            self.run_javascript(
                "if (typeof qt !== 'undefined' && qt.webChannelTransport) {"
                "  new QWebChannel(qt.webChannelTransport, function(channel) {"
                "    channel.objects.backend.get_initial_data(function(json) {"
                "      var data = JSON.parse(json);"
                "      populateSelectors(data.spectra);"
                "      renderResults(data.results);"
                "    });"
                "  });"
                "}"
            )

    def refresh_spectrum_list(self) -> None:
        """Public API: refresh the spectrum selectors."""
        self._on_page_about_to_show(self._page_index)
