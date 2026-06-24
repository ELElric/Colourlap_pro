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
        """Return default RGB primaries and placeholder results as JSON."""
        import json

        return json.dumps(
            {
                "red_xy": [0.6400, 0.3300],
                "green_xy": [0.3000, 0.6000],
                "blue_xy": [0.1500, 0.0600],
                "ratios": {"R": 0.333, "G": 0.333, "B": 0.333},
                "white_xy": [0.3127, 0.3290],
                "white_uv": [0.1978, 0.4683],
                "cct": 6504,
                "results": [
                    {"standard": std, "coverage_1931": 0.0, "match_1931": 0.0,
                     "coverage_1976": 0.0, "match_1976": 0.0}
                    for std in ["sRGB", "NTSC", "DCI-P3", "BT2020"]
                ],
            }
        )

    @Slot(str, result=str)
    def calculate_white_point(self, payload: str) -> str:
        """Compute white point and gamut metrics from RGB xy coordinates."""
        import json
        import traceback

        try:
            data = json.loads(payload)
            red_xy = data["red_xy"]
            green_xy = data["green_xy"]
            blue_xy = data["blue_xy"]
            ratios = data["ratios"]

            def xy_to_xyz(x: float, y: float) -> tuple[float, float, float]:
                if y == 0:
                    return 0.0, 0.0, 0.0
                yy = 1.0
                xx = yy * x / y
                zz = yy * (1.0 - x - y) / y
                return xx, yy, zz

            xyzs = [xy_to_xyz(*c) for c in [red_xy, green_xy, blue_xy]]
            r, g, b = ratios["R"], ratios["G"], ratios["B"]
            mix = [r * xyzs[0][i] + g * xyzs[1][i] + b * xyzs[2][i] for i in range(3)]
            xx, yy, zz = mix
            total = xx + yy + zz
            if total == 0:
                wx = wy = 0.0
            else:
                wx, wy = xx / total, yy / total

            denom = -2.0 * wx + 12.0 * wy + 3.0
            if denom == 0:
                u = v = 0.0
            else:
                u = (4.0 * wx) / denom
                v = (9.0 * wy) / denom

            try:
                import colour

                cct = float(colour.temperature.xy_to_CCT([wx, wy], method="Hernandez 1999"))
            except Exception:  # noqa: BLE001
                cct = 0.0

            from colorlab_pro.dto.color import XY
            from colorlab_pro.engines.gamut_calculator import (
                build_gamut_from_primaries,
                coverage,
                coverage_1976,
                match,
                match_1976,
                standard_gamuts,
            )

            device = build_gamut_from_primaries(
                "Device",
                XY(red_xy[0], red_xy[1]),
                XY(green_xy[0], green_xy[1]),
                XY(blue_xy[0], blue_xy[1]),
                XY(wx, wy),
            )

            results = []
            for std in ["sRGB", "NTSC", "DCI-P3", "BT2020"]:
                try:
                    target = standard_gamuts(std)
                    cov = coverage(target, device)
                    m = match(target, device)
                    cov76 = coverage_1976(target, device)
                    m76 = match_1976(target, device)
                except Exception:  # noqa: BLE001
                    cov = m = cov76 = m76 = 0.0
                results.append(
                    {
                        "standard": std,
                        "coverage_1931": round(cov, 1),
                        "match_1931": round(m, 1),
                        "coverage_1976": round(cov76, 1),
                        "match_1976": round(m76, 1),
                    }
                )

            return json.dumps(
                {
                    "red_xy": red_xy,
                    "green_xy": green_xy,
                    "blue_xy": blue_xy,
                    "ratios": ratios,
                    "white_xy": [round(wx, 4), round(wy, 4)],
                    "white_uv": [round(u, 4), round(v, 4)],
                    "cct": round(cct, 0),
                    "results": results,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})


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

    @Slot(str, result=str)
    def calculate_rgb_ratios(self, payload: str) -> str:
        """Solve RGB mixing ratios to hit a target white point (xy).

        Uses linear least squares in XYZ space with non-negative constraints.
        """
        import json
        import traceback

        try:
            data = json.loads(payload)
            red_xy = data["red_xy"]
            green_xy = data["green_xy"]
            blue_xy = data["blue_xy"]
            target_xy = data["target_xy"]

            def xy_to_xyz(x, y):
                if y == 0:
                    return [0.0, 0.0, 0.0]
                Y = 1.0
                X = Y * x / y
                Z = Y * (1.0 - x - y) / y
                return [X, Y, Z]

            M = [
                xy_to_xyz(*red_xy),
                xy_to_xyz(*green_xy),
                xy_to_xyz(*blue_xy),
            ]
            # Target with unit Y
            target_xyz = xy_to_xyz(*target_xy)

            import numpy as np

            # Non-negative least squares: find weights such that M^T * w ~= target_xyz
            coeffs, residuals, rank, s = np.linalg.lstsq(np.array(M).T, np.array(target_xyz), rcond=None)
            # Clamp negatives to zero and re-normalize so sum = 1
            coeffs = np.maximum(coeffs, 0)
            total = float(np.sum(coeffs))
            if total == 0:
                ratios = {"R": 0.333, "G": 0.333, "B": 0.333}
            else:
                ratios = {"R": round(float(coeffs[0]) / total, 4), "G": round(float(coeffs[1]) / total, 4), "B": round(float(coeffs[2]) / total, 4)}

            # Compute resulting white with these ratios
            calc_payload = json.dumps({
                "red_xy": red_xy, "green_xy": green_xy, "blue_xy": blue_xy, "ratios": ratios
            })
            result = json.loads(self.calculate_white_point(calc_payload))
            result["ratios"] = ratios
            return json.dumps(result)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})


    def page_script(self) -> str:
        return (
            "try {"
            "  new QWebChannel(qt.webChannelTransport, function(channel) {"
            "    channel.objects.backend.get_initial_data(function(json) {"
            "      var data = JSON.parse(json);"
            "      if (data.error) { logStatus('Backend error: ' + data.error); return; }"
            "      if (typeof renderWhitePoint === 'function') renderWhitePoint(data);"
            "      logStatus('Loaded white point data');"
            "    });"
            "  });"
            "} catch (e) { logStatus('JS error: ' + e.message); }"
        )

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
