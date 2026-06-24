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
        optimization_controller: OptimizationController | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_controller = spectrum_controller
        self._color_controller = color_controller
        self._optimization_controller = optimization_controller

    @Slot(result=str)
    def get_initial_data(self) -> str:
        """Return spectra list and placeholder optimization results as JSON."""
        import json

        try:
            summaries = self._spectrum_controller.list_spectra()
            spectra = [
                {"id": s.id, "name": s.name, "category": s.category or "", "channel": s.channel or ""}
                for s in summaries
            ]

            results = [
                {"rank": i + 1, "thickness_r": 1.0 + i * 0.1, "thickness_g": 1.2 + i * 0.1, "thickness_b": 1.4 + i * 0.1, "coverage": 85.0 - i * 2.5, "match": 82.0 - i * 2.5}
                for i in range(5)
            ]

            return json.dumps({"spectra": spectra, "results": results, "best": results[0]})
        except Exception as exc:  # noqa: BLE001
            import traceback

            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})

    @Slot(str, result=str)
    def optimize(self, payload: str) -> str:
        """Run a grid-search thickness optimization and return ranked results."""
        import json
        import traceback

        import numpy as np

        try:
            data = json.loads(payload)
            source_ids = [int(x) for x in data["source_ids"]]
            cf_ids = [int(x) for x in data["cf_ids"]]
            bounds = data["bounds"]  # list of [min,max] for RCF,GCF,BCF
            target_standard = data.get("target_standard", "BT2020")
            target_xy = data.get("target_xy")  # optional [x,y]

            sources = [self._spectrum_controller.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_controller.get_spectrum(sid) for sid in cf_ids]

            from colorlab_pro.dto.color import XY
            from colorlab_pro.dto.spectrum import Spectrum
            from colorlab_pro.engines.gamut_calculator import (
                build_gamut_from_primaries,
                coverage,
                match,
                standard_gamuts,
            )
            from colorlab_pro.engines.spectrum_analyzer import xy as spectrum_xy

            # Use common wavelength grid (source R grid)
            wavelengths = sources[0].wavelengths.copy()
            for s in sources[1:]:
                wavelengths = np.intersect1d(wavelengths, s.wavelengths)
            for c in cfs:
                wavelengths = np.intersect1d(wavelengths, c.wavelengths)
            if len(wavelengths) < 3:
                raise ValueError("Insufficient common wavelength points between spectra")

            def resample(spec: Spectrum) -> Spectrum:
                vals = np.interp(wavelengths, spec.wavelengths, spec.values)
                return Spectrum(wavelengths=wavelengths, values=vals, unit=spec.unit)

            sources = [resample(s) for s in sources]
            cfs = [resample(c) for c in cfs]

            def transmittance_to_alpha(t: np.ndarray) -> np.ndarray:
                # Handle percent (0-100) or fractional (0-1)
                t = np.asarray(t, dtype=float)
                if np.max(t) > 1.5:
                    t = t / 100.0
                t = np.clip(t, 1e-6, 1.0)
                return -np.log10(t)

            alphas = [transmittance_to_alpha(c.values) for c in cfs]

            if target_xy is not None:
                target = XY(float(target_xy[0]), float(target_xy[1]))
            else:
                target = standard_gamuts(target_standard).white
                target = XY(target[0], target[1])

            target_gamut = standard_gamuts(target_standard)

            # Grid search (3 steps per channel => 27 combos)
            steps = 4
            candidates = []
            for dr in np.linspace(bounds[0][0], bounds[0][1], steps):
                for dg in np.linspace(bounds[1][0], bounds[1][1], steps):
                    for db in np.linspace(bounds[2][0], bounds[2][1], steps):
                        filtered = []
                        for src, alpha, d in zip(sources, alphas, [dr, dg, db], strict=False):
                            t = np.power(10.0, -alpha * d)
                            filtered.append(src.values * t)
                        white = Spectrum(
                            wavelengths=wavelengths,
                            values=sum(filtered),
                            unit=sources[0].unit,
                        )
                        white_xy = spectrum_xy(white)
                        delta = float(np.hypot(white_xy.x - target.x, white_xy.y - target.y))

                        primaries_xy = [spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=sources[0].unit)) for v in filtered]
                        device = build_gamut_from_primaries(
                            "Device",
                            primaries_xy[0],
                            primaries_xy[1],
                            primaries_xy[2],
                            white_xy,
                        )
                        cov = coverage(target_gamut, device)
                        m = match(target_gamut, device)
                        candidates.append(
                            {
                                "thickness_r": round(float(dr), 3),
                                "thickness_g": round(float(dg), 3),
                                "thickness_b": round(float(db), 3),
                                "white_xy": [round(white_xy.x, 4), round(white_xy.y, 4)],
                                "delta_xy": round(delta, 4),
                                "coverage": round(cov, 1),
                                "match": round(m, 1),
                            }
                        )

            # Sort by closeness to target white, then coverage
            candidates.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
            top = candidates[:5]
            for i, r in enumerate(top):
                r["rank"] = i + 1

            return json.dumps({"results": top, "best": top[0] if top else None})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "trace": traceback.format_exc()})



    @Slot(str, result=str)
    def sensitivity_analysis(self, payload: str) -> str:
        """Vary one CF thickness at a time and return coverage / white point drift."""
        import json
        import traceback

        import numpy as np

        try:
            data = json.loads(payload)
            base = data["base"]
            vary_channel = data["vary_channel"]
            source_ids = [int(x) for x in data["source_ids"]]
            cf_ids = [int(x) for x in data["cf_ids"]]
            bounds = data["bounds"]

            sources = [self._spectrum_controller.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_controller.get_spectrum(sid) for sid in cf_ids]

            from colorlab_pro.dto.spectrum import Spectrum
            from colorlab_pro.engines.gamut_calculator import (
                build_gamut_from_primaries,
                coverage,
                standard_gamuts,
            )
            from colorlab_pro.engines.spectrum_analyzer import xy as spectrum_xy

            wavelengths = sources[0].wavelengths.copy()
            for s in sources[1:]:
                wavelengths = np.intersect1d(wavelengths, s.wavelengths)
            for c in cfs:
                wavelengths = np.intersect1d(wavelengths, c.wavelengths)

            def resample(spec):
                vals = np.interp(wavelengths, spec.wavelengths, spec.values)
                return Spectrum(wavelengths=wavelengths, values=vals, unit=spec.unit)

            sources = [resample(s) for s in sources]
            cfs = [resample(c) for c in cfs]

            def transmittance_to_alpha(t):
                t = np.asarray(t, dtype=float)
                if np.max(t) > 1.5:
                    t = t / 100.0
                t = np.clip(t, 1e-6, 1.0)
                return -np.log10(t)

            alphas = [transmittance_to_alpha(c.values) for c in cfs]
            target = standard_gamuts("BT2020")
            channel_idx = {"R": 0, "G": 1, "B": 2}[vary_channel]
            lo, hi = bounds[channel_idx]

            points = []
            for d in np.linspace(lo, hi, 21):
                ds = [base[0], base[1], base[2]]
                ds[channel_idx] = d
                filtered = []
                for src, alpha, dd in zip(sources, alphas, ds, strict=False):
                    t = np.power(10.0, -alpha * dd)
                    filtered.append(src.values * t)
                primaries_xy = [spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=sources[0].unit)) for v in filtered]
                white = Spectrum(wavelengths=wavelengths, values=sum(filtered), unit=sources[0].unit)
                white_xy = spectrum_xy(white)
                device = build_gamut_from_primaries("Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy)
                cov = coverage(target, device)
                points.append({
                    "thickness": round(float(d), 3),
                    "coverage": round(float(cov), 1),
                    "white_x": round(float(white_xy.x), 4),
                    "white_y": round(float(white_xy.y), 4),
                })
            return json.dumps({"channel": vary_channel, "points": points})
        except Exception as exc:  # noqa: BLE001
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
        return (
            "try {"
            "  new QWebChannel(qt.webChannelTransport, function(channel) {"
            "    channel.objects.backend.get_initial_data(function(json) {"
            "      var data = JSON.parse(json);"
            "      if (data.error) { logStatus('Backend error: ' + data.error); return; }"
            "      populateSelectors(data.spectra);"
            "      renderResults(data.results, data.best);"
            "      logStatus('Loaded optimizer data');"
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
