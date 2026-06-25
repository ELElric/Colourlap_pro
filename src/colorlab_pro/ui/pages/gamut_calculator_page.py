"""Web-based Gamut Calculator page."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import cast

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QWidget

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.exporters.report_exporter import ReportExporter
from colorlab_pro.ui.webview_page import WebViewPage
from colorlab_pro.utils.validation import validate_spectrum_id


def _sample_points(spectrum, step: int = 5) -> list[list[float]]:
    """Return a down-sampled list of [wavelength, value] for charting."""
    if spectrum is None or len(spectrum.wavelengths) == 0:
        return []
    return [
        [round(float(w), 1), round(float(v), 4)]
        for w, v in zip(spectrum.wavelengths[::step], spectrum.values[::step], strict=False)
    ]


class GamutPageBackend(QObject):
    """Backend exposed to the Gamut Calculator page JavaScript."""

    calculation_started = Signal()
    calculation_finished = Signal()

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_controller = spectrum_controller
        self._color_controller = color_controller
        self._last_primaries: list[dict] = [
            {"ch": "R", "x": 0.0, "y": 0.0},
            {"ch": "G", "x": 0.0, "y": 0.0},
            {"ch": "B", "x": 0.0, "y": 0.0},
        ]
        self._last_results: list[dict] = []

    def _spectra_json(self) -> list[dict]:
        summaries = self._spectrum_controller.list_spectra()
        return [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category or "",
                "channel": s.channel or "",
                "data": _sample_points(self._spectrum_controller.get_spectrum(s.id)),
            }
            for s in summaries
        ]

    @Slot(result=str)
    def get_initial_data(self) -> str:
        """Return spectra list and empty gamut results as JSON."""
        try:
            return json.dumps({"spectra": self._spectra_json(), "results": []})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})

    @staticmethod
    def _apply_cf_filter(
        spectrum: Spectrum,
        cf_spectrum: Spectrum | None,
        thickness: float,
    ) -> Spectrum:
        """Apply Color Filter + thickness (Lambert-Beer) to a spectrum.

        If cf_spectrum is None or thickness <= 0, returns the original spectrum.
        """
        if cf_spectrum is None or thickness <= 0:
            return spectrum
        wl = spectrum.wavelengths
        cf_wl = cf_spectrum.wavelengths
        cf_val = cf_spectrum.values
        t = np.interp(wl, cf_wl, cf_val, left=1.0, right=1.0)
        t = np.where(t > 1.5, t / 100.0, t)
        t = np.clip(t, 1e-6, 1.0)
        alpha = -np.log10(t)
        attenuation = np.exp(-alpha * thickness)
        filtered = spectrum.values * attenuation
        return Spectrum(wavelengths=wl, values=filtered, unit=spectrum.unit, meta=spectrum.meta)

    @Slot(str, str, str, result=str)
    def calculate_gamut(self, red_id: str, green_id: str = "", blue_id: str = "") -> str:
        """Calculate gamut coverage/match for the selected RGB spectra.

        Accepts either three spectrum IDs (legacy call) or a JSON payload as
        the first argument with keys:
            red_id, green_id, blue_id (required)
            cf_red_id, cf_green_id, cf_blue_id (optional)
            thickness_r, thickness_g, thickness_b (optional, default 0)
        """
        self.calculation_started.emit()
        try:
            # Support both JSON payload and legacy 3-argument calls
            try:
                data = json.loads(red_id)
                if not isinstance(data, dict):
                    raise ValueError("Payload must be a JSON object")
            except (json.JSONDecodeError, ValueError):
                data = {"red_id": red_id, "green_id": green_id, "blue_id": blue_id}
            red_id = data["red_id"]
            green_id = data["green_id"]
            blue_id = data["blue_id"]
            ids = [
                validate_spectrum_id(red_id),
                validate_spectrum_id(green_id),
                validate_spectrum_id(blue_id),
            ]
            specs = [self._spectrum_controller.get_spectrum(sid) for sid in ids]
            if any(s is None for s in specs):
                raise ValueError("One or more selected spectra were not found")

            def _load_cf(cf_id: str) -> Spectrum | None:
                if not cf_id:
                    return None
                try:
                    sid = validate_spectrum_id(cf_id)
                    return self._spectrum_controller.get_spectrum(sid)
                except Exception:  # noqa: BLE001
                    return None

            cf_specs = [
                _load_cf(data.get("cf_red_id", "")),
                _load_cf(data.get("cf_green_id", "")),
                _load_cf(data.get("cf_blue_id", "")),
            ]
            thicknesses = [
                float(data.get("thickness_r", 0)),
                float(data.get("thickness_g", 0)),
                float(data.get("thickness_b", 0)),
            ]

            mode = data.get("mode", "rgbcf")
            gs = self._color_controller._gamut_service()

            if mode == "whitecf":
                white_id = data.get("white_id", "")
                if not white_id:
                    raise ValueError("White spectrum is required for White + Color Filter mode")
                white_spec = self._spectrum_controller.get_spectrum(validate_spectrum_id(white_id))
                if white_spec is None:
                    raise ValueError("Selected white spectrum not found")

                filtered_specs = []
                for i in range(3):
                    cf = cf_specs[i]
                    thickness = thicknesses[i]
                    if cf is None or thickness <= 0:
                        filtered_specs.append(white_spec)
                        continue
                    cf_filtered = self._apply_cf_filter(white_spec, cf, thickness)
                    filtered_specs.append(cf_filtered)

                device = gs.build_from_primaries(
                    filtered_specs[0], filtered_specs[1], filtered_specs[2],
                    white=white_spec, name="Device"
                )
            else:
                filtered_specs = [
                    self._apply_cf_filter(cast(Spectrum, specs[i]), cf_specs[i], thicknesses[i])
                    for i in range(3)
                ]
                device = gs.build_from_primaries(
                    filtered_specs[0], filtered_specs[1], filtered_specs[2], name="Device"
                )

            def _xy_to_xyz(x, y):
                if y == 0:
                    return (0.0, 0.0, 0.0)
                return (x / y, 1.0, (1.0 - x - y) / y)

            def _cct_from_xy(x, y):
                try:
                    import colour

                    return round(
                        float(colour.temperature.xy_to_CCT([x, y], method="Hernandez 1999")), 0
                    )
                except Exception:
                    return 0

            primaries = []
            for ch, xy_pt in [("R", device.red), ("G", device.green), ("B", device.blue)]:
                x, y = round(xy_pt[0], 4), round(xy_pt[1], 4)
                xyz = _xy_to_xyz(x, y)
                primaries.append(
                    {
                        "ch": ch,
                        "x": x,
                        "y": y,
                        "X": round(xyz[0], 4),
                        "Y": round(xyz[1], 4),
                        "Z": round(xyz[2], 4),
                        "cct": _cct_from_xy(x, y),
                    }
                )
            self._last_primaries = primaries

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
            self._last_results = results

            return json.dumps({"primaries": primaries, "results": results})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})
        finally:
            self.calculation_finished.emit()

    @Slot(str, result=str)
    def compare_configurations(self, payload: str) -> str:
        """Compare multiple RGB+CF configurations and return ranked results."""
        import json
        import traceback

        self.calculation_started.emit()
        try:
            data = json.loads(payload)
            configs = data["configs"]  # list of {name, red_id, green_id, blue_id}
            gs = self._color_controller._gamut_service()
            results = []
            for cfg in configs:
                ids = [
                    validate_spectrum_id(cfg["red_id"]),
                    validate_spectrum_id(cfg["green_id"]),
                    validate_spectrum_id(cfg["blue_id"]),
                ]
                specs = [self._spectrum_controller.get_spectrum(sid) for sid in ids]
                if any(s is None for s in specs):
                    continue
                device = gs.build_from_primaries(specs[0], specs[1], specs[2], name=cfg["name"])
                try:
                    cov = gs.coverage("BT2020", device)
                    match = gs.match("BT2020", device)
                except Exception:  # noqa: BLE001
                    cov = match = 0.0
                results.append(
                    {
                        "name": cfg["name"],
                        "coverage": round(cov, 1),
                        "match": round(match, 1),
                        "red_xy": [round(device.red[0], 4), round(device.red[1], 4)],
                        "green_xy": [round(device.green[0], 4), round(device.green[1], 4)],
                        "blue_xy": [round(device.blue[0], 4), round(device.blue[1], 4)],
                    }
                )
            results.sort(key=lambda x: (-x["coverage"], -x["match"]))
            return json.dumps({"results": results})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})
        finally:
            self.calculation_finished.emit()

    @Slot(str, result=str)
    def export_report(self, payload: str) -> str:
        """Generate an HTML report from current gamut results and return file path."""
        import json
        import traceback
        from pathlib import Path

        try:
            data = json.loads(payload)
            parent = self.parent()
            path_str, _ = QFileDialog.getSaveFileName(
                parent,
                "Export Gamut Report",
                "colorlab_gamut_report.html",
                "HTML Files (*.html);;All Files (*)",
            )
            if not path_str:
                return json.dumps({"cancelled": True})
            exporter = ReportExporter()
            out = Path(path_str)
            exporter.export_gamut_report(
                data.get("primaries") or self._last_primaries,
                data.get("results") or self._last_results,
                out,
                title=data.get("title", "Gamut Analysis Report"),
            )
            return json.dumps({"path": str(out.resolve())})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})

    @Slot(str, result=str)
    def paste_spectrum(self, payload: str) -> str:
        """Parse clipboard text and save as a new spectrum."""
        import json
        import traceback

        try:
            data = json.loads(payload)
            from colorlab_pro.ui.utils.clipboard_parser import parse_spectrum_from_text

            spectrum = parse_spectrum_from_text(data.get("text", ""))
            name = data.get("name", "Pasted Spectrum")
            if spectrum.meta is None:
                spectrum.meta = {}
            spectrum.meta["name"] = name
            sid = self._spectrum_controller.import_spectrum(spectrum, name=name, category="Pasted")
            if sid is None:
                return json.dumps({"error": "Failed to import pasted spectrum"})
            return json.dumps({"id": sid})
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
