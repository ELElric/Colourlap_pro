"""Web-based White Point page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QWidget

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.ui.webview_page import WebViewPage


class WhitePointPageBackend(QObject):
    """Backend exposed to the White Point page JavaScript."""

    def __init__(
        self,
        color_controller: ColorController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_controller = color_controller

    @Slot(result=str)
    def get_initial_data(self) -> str:
        """Return placeholder white point data as JSON."""
        import json

        return json.dumps(
            {
                "red_xy": [0.6400, 0.3300],
                "green_xy": [0.3000, 0.6000],
                "blue_xy": [0.1500, 0.0600],
                "white_xy": [0.3127, 0.3290],
                "white_uv": [0.1978, 0.4683],
                "cct": 6504,
                "ratio": {"R": 0.30, "G": 0.59, "B": 0.11},
            }
        )


class WhitePointPage(WebViewPage):
    """White Point workspace page rendered as HTML."""

    white_point_calculated = Signal(object)

    def __init__(
        self,
        color_controller: ColorController | None = None,
        page_index: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        if color_controller is None:
            raise ValueError("ColorController is required")
        super().__init__(parent)
        self._color_controller = color_controller
        self._page_index = page_index
        self.initialize()

    def html_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "web" / "white_point_page.html"

    def create_backend(self) -> QObject:
        return WhitePointPageBackend(self._color_controller, self)

    def page_script(self) -> str:
        return """
        if (typeof qt === 'undefined' || !qt.webChannelTransport) {
            console.error('QWebChannel transport not available');
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            channel.objects.backend.get_initial_data(function(json) {
                var data = JSON.parse(json);
                if (typeof renderWhitePoint === 'function') renderWhitePoint(data);
                if (typeof logStatus === 'function') logStatus('Loaded white point data');
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
                            if (typeof renderWhitePoint === 'function') renderWhitePoint(JSON.parse(json));
                        });
                    });
                }
            """)

    def set_rgb_coordinates(self, r_xy, g_xy, b_xy) -> None:
        """Receive RGB coordinates from the Gamut Calculator page."""
        import json

        data = {
            "red_xy": [r_xy.x, r_xy.y],
            "green_xy": [g_xy.x, g_xy.y],
            "blue_xy": [b_xy.x, b_xy.y],
        }
        self.run_javascript(f"if (typeof setRGBCoordinates === 'function') setRGBCoordinates({json.dumps(data)});")

    def get_rgb_coordinates(self):
        """Public API: currently not used."""
        return None
