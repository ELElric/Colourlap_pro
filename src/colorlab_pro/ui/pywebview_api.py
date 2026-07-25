"""pywebview API 桥接类.

将四个页面的 Backend 方法统一到一个类中，通过 pywebview 的 js_api 暴露给前端。

关键差异 (vs 原有 QWebChannel Backend):
- 方法名加前缀 (spectrum_ / gamut_ / whitepoint_ / optimizer_) 避免冲突
- 去掉所有 @Slot 装饰器，使用 pywebview 原生调用
- 去掉所有 json.dumps / json.loads（pywebview 自动处理 JSON 序列化）
- QFileDialog 替换为 tkinter.filedialog
- QCoreApplication.processEvents() 替换为 threading
"""

from __future__ import annotations

import math
import threading
import time
import traceback
from pathlib import Path
from typing import Any, cast

import numpy as np

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.exporters.report_exporter import ReportExporter
from colorlab_pro.ui.utils.clipboard_parser import parse_spectrum_from_text
from colorlab_pro.utils.validation import validate_ratio, validate_spectrum_id, validate_xy


# ================================================================== #
# Helpers
# ================================================================== #


def _sample_points(spectrum, step: int = 5) -> list[list[float]]:
    """Return a down-sampled list of [wavelength, value] for charting.

    Values are rounded to 6 significant figures so that very small spectral
    intensities (e.g. QD emissions ~1e-5) are not truncated to zero.
    """
    if spectrum is None or len(spectrum.wavelengths) == 0:
        return []

    def _sig(v: float) -> float:
        if v == 0:
            return 0.0
        decimals = 5 - int(math.floor(math.log10(abs(v))))
        return round(v, max(decimals, 0))

    return [
        [round(float(w), 1), _sig(float(v))]
        for w, v in zip(spectrum.wavelengths[::step], spectrum.values[::step], strict=False)
    ]


def _safe_error(exc: Exception) -> dict[str, Any]:
    """Return a standardized error dict."""
    return {"error": str(exc), "trace": traceback.format_exc()}


def _tk_file_dialog_open(
    title: str = "Open",
    filetypes: list[tuple[str, str]] | None = None,
) -> str | None:
    """Open a file dialog using tkinter (works without Qt event loop)."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if filetypes is None:
            filetypes = [("All Files", "*")]
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        root.destroy()
        return path or None
    except Exception:  # noqa: BLE001
        return None


def _tk_file_dialog_save(
    title: str = "Save",
    default_name: str = "",
    filetypes: list[tuple[str, str]] | None = None,
) -> str | None:
    """Save file dialog using tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if filetypes is None:
            filetypes = [("All Files", "*")]
        path = filedialog.asksaveasfilename(title=title, defaultextension=default_name, filetypes=filetypes)
        root.destroy()
        return path or None
    except Exception:  # noqa: BLE001
        return None


def _tk_directory_dialog(title: str = "Select Directory") -> str | None:
    """Directory selection dialog using tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title=title)
        root.destroy()
        return path or None
    except Exception:  # noqa: BLE001
        return None


# ================================================================== #
# ColorLab API
# ================================================================== #


class ColorLabApi:
    """Unified API exposed to pywebview JavaScript.

    所有方法前缀:
      spectrum_   — 光谱库页面
      gamut_      — 色域计算器页面
      whitepoint_ — 白点计算器页面
      optimizer_  — 膜厚优化页面

    pywebview 自动将 Python dict/list 序列化为 JSON，将 JSON 参数
    反序列化为 Python dict/list，因此不需要手动 json.dumps / json.loads。
    """

    def __init__(self, main_ctrl: MainController) -> None:
        self._main_ctrl = main_ctrl

        # Create sub-controllers (they need QApplication.instance(), which
        # app_pywebview.py ensures exists before this point)
        self._spectrum_ctrl = SpectrumController(main_ctrl)
        self._color_ctrl = ColorController(main_ctrl)
        self._opt_ctrl = OptimizationController(main_ctrl)

        # Optimizer state
        self._stop_event = threading.Event()

        # Gamut page state
        self._last_primaries: list[dict] = [
            {"ch": "R", "x": 0.0, "y": 0.0},
            {"ch": "G", "x": 0.0, "y": 0.0},
            {"ch": "B", "x": 0.0, "y": 0.0},
        ]
        self._last_results: list[dict] = []

    # -------------------------------------------------------------- #
    # Spectrum page methods
    # -------------------------------------------------------------- #

    def spectrum_get_spectra(self) -> list[dict] | dict:
        """Return the spectrum list with pre-computed summary fields."""
        try:
            summaries = self._spectrum_ctrl.list_spectra()
            spectra: list[dict] = []
            for s in summaries:
                full_spec = self._spectrum_ctrl.get_spectrum(s.id)
                spectra.append(
                    {
                        "id": s.id,
                        "name": s.name,
                        "category": s.category or "",
                        "channel": s.channel or "",
                        "peak_nm": s.peak_wavelength if s.peak_wavelength is not None else None,
                        "fwhm_nm": s.fwhm if s.fwhm is not None else None,
                        "thickness_um": (
                            round(s.thickness_um, 3) if s.thickness_um is not None else None
                        ),
                        "xy": s.xy_str or "-",
                        "uv": s.uv_str or "-",
                        "dominant_nm": s.dominant_wavelength_str or "-",
                        "purity": s.purity_str or "-",
                        "data": _sample_points(full_spec),
                    }
                )
            return spectra
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def spectrum_delete_spectra(self, ids: list[int]) -> dict:
        """Delete selected spectra. Returns {deleted: int} or {error}."""
        try:
            deleted = 0
            for sid in ids:
                if self._spectrum_ctrl.delete_spectrum(sid):
                    deleted += 1
            return {"deleted": deleted}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def spectrum_import_spectra(self, category: str = "") -> dict:
        """Open a file dialog and import CSV/XLSX/TXT spectra."""
        path_str = _tk_file_dialog_open(
            title="Import Spectrum",
            filetypes=[
                ("Spectrum Files", "*.csv *.xlsx *.txt"),
                ("All Files", "*"),
            ],
        )
        if not path_str:
            return {"ids": [], "cancelled": True}
        path = Path(path_str)
        try:
            suffix = path.suffix.lower()
            if suffix == ".xlsx":
                result = self._spectrum_ctrl.import_xlsx_file(path, category=category)
            else:
                result = self._spectrum_ctrl.import_csv_file(path, category=category)
            ids = result if isinstance(result, list) else ([result] if result else [])
            return {"ids": [i for i in ids if i is not None]}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def spectrum_export_selected(self, ids: list[int]) -> dict:
        """Export selected spectra to a user-chosen directory."""
        if not ids:
            return {"error": "No spectra selected"}
        dir_str = _tk_directory_dialog(title="Export Spectra")
        if not dir_str:
            return {"cancelled": True}
        from colorlab_pro.exporters.csv_exporter import export_spectrum

        out_dir = Path(dir_str)
        exported = 0
        for sid in ids:
            spec = self._spectrum_ctrl.get_spectrum(sid)
            if spec is None:
                continue
            name = spec.meta.get("name", f"spectrum_{sid}") if spec.meta else f"spectrum_{sid}"
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            export_spectrum(spec, out_dir / f"{safe_name}.csv")
            exported += 1
        return {"path": str(out_dir), "exported": exported}

    def spectrum_paste_spectrum(self, payload: dict) -> dict:
        """Parse clipboard text and save as a new spectrum."""
        try:
            text = payload.get("text", "")
            name = payload.get("name", "Pasted Spectrum")
            spectrum = parse_spectrum_from_text(text)
            if spectrum.meta is None:
                spectrum.meta = {}
            spectrum.meta["name"] = name
            spectrum.meta["category"] = spectrum.meta.get("category", "Pasted")
            sid = self._spectrum_ctrl.import_spectrum(spectrum, name=name, category="Pasted")
            if sid is None:
                return {"error": "Failed to import pasted spectrum"}
            return {"id": sid}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def spectrum_update_spectrum(self, data: dict) -> dict:
        """Update editable fields of a spectrum (name, category, channel, thickness_um)."""
        try:
            sid = int(data["id"])
            ok = True
            if "name" in data:
                ok = ok and self._spectrum_ctrl.rename_spectrum(sid, str(data["name"]))
            if "category" in data:
                ok = ok and self._spectrum_ctrl.update_category(sid, str(data["category"]))
            if "channel" in data:
                ok = ok and self._spectrum_ctrl.update_channel(sid, str(data["channel"]))
            if "thickness_um" in data:
                val = data["thickness_um"]
                thickness = float(val) if val is not None and val != "" else None
                ok = ok and self._spectrum_ctrl.update_thickness(sid, thickness)
            return {"ok": ok}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    # -------------------------------------------------------------- #
    # Gamut Calculator page methods
    # -------------------------------------------------------------- #

    def _gamut_spectra_json(self) -> list[dict]:
        """Return spectra list for gamut page selectors."""
        summaries = self._spectrum_ctrl.list_spectra()
        return [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category or "",
                "channel": s.channel or "",
                "data": _sample_points(self._spectrum_ctrl.get_spectrum(s.id)),
            }
            for s in summaries
        ]

    def gamut_get_initial_data(self) -> dict:
        """Return spectra list and empty gamut results."""
        try:
            return {"spectra": self._gamut_spectra_json(), "results": []}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    @staticmethod
    def _apply_cf_filter(
        spectrum: Spectrum,
        cf_spectrum: Spectrum | None,
        thickness: float,
    ) -> Spectrum:
        """Apply Color Filter + thickness (Lambert-Beer) to a spectrum."""
        if cf_spectrum is None:
            return spectrum
        wl = spectrum.wavelengths
        cf_wl = cf_spectrum.wavelengths
        cf_val = cf_spectrum.values
        t = np.interp(wl, cf_wl, cf_val, left=1.0, right=1.0)
        t = np.where(t > 1.5, t / 100.0, t)
        t = np.clip(t, 1e-6, 1.0)
        attenuation = np.power(t, max(thickness, 0.0))
        filtered = spectrum.values * attenuation
        return Spectrum(wavelengths=wl, values=filtered, unit=spectrum.unit, meta=spectrum.meta)

    def gamut_calculate(self, payload: dict) -> dict:
        """Calculate gamut coverage/match for the selected RGB spectra."""
        try:
            mode = payload.get("mode", "rgbcf")
            gs = self._color_ctrl._gamut_service()

            def _load_cf(cf_id: str) -> Spectrum | None:
                if not cf_id:
                    return None
                try:
                    sid = validate_spectrum_id(cf_id)
                    return self._spectrum_ctrl.get_spectrum(sid)
                except Exception:  # noqa: BLE001
                    return None

            cf_specs = [
                _load_cf(payload.get("cf_red_id", "")),
                _load_cf(payload.get("cf_green_id", "")),
                _load_cf(payload.get("cf_blue_id", "")),
            ]
            thicknesses = [
                float(payload.get("thickness_r", 0)),
                float(payload.get("thickness_g", 0)),
                float(payload.get("thickness_b", 0)),
            ]

            if mode == "whitecf":
                white_id = payload.get("white_id", "")
                if not white_id:
                    raise ValueError("White spectrum is required for White + Color Filter mode")
                white_spec = self._spectrum_ctrl.get_spectrum(validate_spectrum_id(white_id))
                if white_spec is None:
                    raise ValueError("Selected white spectrum not found")

                filtered_specs = []
                for i in range(3):
                    cf = cf_specs[i]
                    thickness = thicknesses[i]
                    filtered_specs.append(self._apply_cf_filter(white_spec, cf, thickness))

                device = gs.build_from_primaries(
                    filtered_specs[0], filtered_specs[1], filtered_specs[2],
                    white=white_spec, name="Device",
                )
            else:
                red_id = payload.get("red_id", "")
                green_id = payload.get("green_id", "")
                blue_id = payload.get("blue_id", "")
                ids = [
                    validate_spectrum_id(red_id),
                    validate_spectrum_id(green_id),
                    validate_spectrum_id(blue_id),
                ]
                specs = [self._spectrum_ctrl.get_spectrum(sid) for sid in ids]
                if any(s is None for s in specs):
                    raise ValueError("One or more selected spectra were not found")
                filtered_specs = [
                    self._apply_cf_filter(cast(Spectrum, specs[i]), cf_specs[i], thicknesses[i])
                    for i in range(3)
                ]
                device = gs.build_from_primaries(
                    filtered_specs[0], filtered_specs[1], filtered_specs[2], name="Device",
                )

            def _xy_to_xyz(x, y):
                if y == 0:
                    return (0.0, 0.0, 0.0)
                return (x / y, 1.0, (1.0 - x - y) / y)

            def _cct_from_xy(x, y):
                try:
                    import colour
                    return round(float(colour.temperature.xy_to_CCT([x, y], method="Hernandez 1999")), 0)
                except Exception:
                    return None

            primaries = []
            for idx, (ch, xy_pt) in enumerate([("R", device.red), ("G", device.green), ("B", device.blue)]):
                x, y = round(xy_pt[0], 4), round(xy_pt[1], 4)
                xyz = _xy_to_xyz(x, y)
                sp = filtered_specs[idx]
                try:
                    peak_nm = float(sp.wavelengths[np.argmax(sp.values)])
                    peak_val = float(np.max(sp.values))
                    half_max = peak_val / 2.0
                    above_half = sp.values >= half_max
                    if np.any(above_half):
                        indices = np.where(above_half)[0]
                        fwhm_nm = float(sp.wavelengths[indices[-1]] - sp.wavelengths[indices[0]])
                    else:
                        fwhm_nm = None
                except Exception:
                    peak_nm, fwhm_nm = None, None
                try:
                    dominant_nm = peak_nm
                    import colour

                    wl_cmfs = colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"]
                    best_nm, best_dist = None, float("inf")
                    for w in range(380, 781, 5):
                        cmf = wl_cmfs[np.float64(w)]
                        lx = float(cmf[0] / (cmf[0] + cmf[1] + cmf[2]))
                        ly = float(cmf[1] / (cmf[0] + cmf[1] + cmf[2]))
                        d = (lx - x) ** 2 + (ly - y) ** 2
                        if d < best_dist:
                            best_dist = d
                            best_nm = w
                    dominant_nm = best_nm
                    try:
                        cmf = wl_cmfs[np.float64(dominant_nm)]
                        lx = float(cmf[0] / (cmf[0] + cmf[1] + cmf[2]))
                        ly = float(cmf[1] / (cmf[0] + cmf[1] + cmf[2]))
                        wx, wy = 0.3127, 0.3290
                        dist_cw = math.sqrt((x - wx) ** 2 + (y - wy) ** 2)
                        dist_lw = math.sqrt((lx - wx) ** 2 + (ly - wy) ** 2)
                        purity = (dist_cw / dist_lw * 100) if dist_lw > 0.001 else None
                    except Exception:
                        purity = None
                except Exception:
                    dominant_nm, purity = None, None
                primaries.append(
                    {
                        "ch": ch,
                        "x": x,
                        "y": y,
                        "X": round(xyz[0], 4),
                        "Y": round(xyz[1], 4),
                        "Z": round(xyz[2], 4),
                        "cct": _cct_from_xy(x, y),
                        "peak_nm": peak_nm,
                        "fwhm_nm": fwhm_nm,
                        "dominant_nm": dominant_nm,
                        "purity": round(purity, 1) if purity is not None else None,
                    }
                )
            self._last_primaries = primaries

            results = []
            for std in ["sRGB", "NTSC", "DCI-P3", "BT2020"]:
                try:
                    cov = gs.coverage(std, device)
                    m = gs.match(std, device)
                    cov_1976 = gs.coverage_1976(std, device)
                    m_1976 = gs.match_1976(std, device)
                except Exception:  # noqa: BLE001
                    cov = m = cov_1976 = m_1976 = 0.0
                results.append(
                    {
                        "standard": std,
                        "coverage_1931": round(cov, 1),
                        "match_1931": round(m, 1),
                        "coverage_1976": round(cov_1976, 1),
                        "match_1976": round(m_1976, 1),
                    }
                )
            self._last_results = results

            try:
                wx = float(device.white[0])
                wy = float(device.white[1])
            except Exception:
                wx, wy = 0.0, 0.0

            return {"primaries": primaries, "results": results, "white_xy": [round(wx, 4), round(wy, 4)]}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def gamut_compare_configurations(self, payload: dict) -> dict:
        """Compare multiple RGB+CF configurations and return ranked results."""
        try:
            configs = payload["configs"]
            gs = self._color_ctrl._gamut_service()
            results = []
            for cfg in configs:
                ids = [
                    validate_spectrum_id(cfg["red_id"]),
                    validate_spectrum_id(cfg["green_id"]),
                    validate_spectrum_id(cfg["blue_id"]),
                ]
                specs = [self._spectrum_ctrl.get_spectrum(sid) for sid in ids]
                if any(s is None for s in specs):
                    continue
                device = gs.build_from_primaries(specs[0], specs[1], specs[2], name=cfg["name"])
                try:
                    cov = gs.coverage("BT2020", device)
                    m = gs.match("BT2020", device)
                except Exception:  # noqa: BLE001
                    cov = m = 0.0
                results.append(
                    {
                        "name": cfg["name"],
                        "coverage": round(cov, 1),
                        "match": round(m, 1),
                        "red_xy": [round(device.red[0], 4), round(device.red[1], 4)],
                        "green_xy": [round(device.green[0], 4), round(device.green[1], 4)],
                        "blue_xy": [round(device.blue[0], 4), round(device.blue[1], 4)],
                    }
                )
            results.sort(key=lambda x: (-x["coverage"], -x["match"]))
            return {"results": results}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def gamut_export_report(self, payload: dict) -> dict:
        """Generate an HTML report from current gamut results and return file path."""
        try:
            path_str = _tk_file_dialog_save(
                title="Export Gamut Report",
                default_name="colorlab_gamut_report.html",
                filetypes=[("HTML Files", "*.html"), ("All Files", "*")],
            )
            if not path_str:
                return {"cancelled": True}
            exporter = ReportExporter()
            out = Path(path_str)
            exporter.export_gamut_report(
                payload.get("primaries") or self._last_primaries,
                payload.get("results") or self._last_results,
                out,
                title=payload.get("title", "Gamut Analysis Report"),
            )
            return {"path": str(out.resolve())}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def gamut_paste_spectrum(self, payload: dict) -> dict:
        """Parse clipboard text and save as a new spectrum (gamut page version)."""
        try:
            text = payload.get("text", "")
            name = payload.get("name", "Pasted Spectrum")
            spectrum = parse_spectrum_from_text(text)
            if spectrum.meta is None:
                spectrum.meta = {}
            spectrum.meta["name"] = name
            sid = self._spectrum_ctrl.import_spectrum(spectrum, name=name, category="Pasted")
            if sid is None:
                return {"error": "Failed to import pasted spectrum"}
            return {"id": sid}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    # -------------------------------------------------------------- #
    # White Point page methods
    # -------------------------------------------------------------- #

    def whitepoint_get_initial_data(self) -> dict:
        """Return default RGB primaries and empty results."""
        return {
            "red_xy": [0.6400, 0.3300],
            "green_xy": [0.300, 0.600],
            "blue_xy": [0.150, 0.060],
            "ratios": [0.3333, 0.3333, 0.3333],
            "white_xy": [0.3127, 0.329],
            "white_uv": [0.1978, 0.4683],
            "cct": 6504,
            "results": [],
        }

    @staticmethod
    def _xy_to_xyz(x: float, y: float) -> tuple[float, float, float]:
        if y == 0:
            return 0.0, 0.0, 0.0
        yy = 1.0
        xx = yy * x / y
        zz = yy * (1.0 - x - y) / y
        return xx, yy, zz

    def whitepoint_calculate(self, payload: dict) -> dict:
        """Compute white point and gamut metrics from RGB xy coordinates."""
        try:
            red_xy = validate_xy(payload["red_xy"], "red_xy")
            green_xy = validate_xy(payload["green_xy"], "green_xy")
            blue_xy = validate_xy(payload["blue_xy"], "blue_xy")
            ratios = {
                "R": validate_ratio(payload["ratios"]["R"], "R ratio"),
                "G": validate_ratio(payload["ratios"]["G"], "G ratio"),
                "B": validate_ratio(payload["ratios"]["B"], "B ratio"),
            }

            xyzs = [self._xy_to_xyz(*c) for c in [red_xy, green_xy, blue_xy]]
            r, g, b = ratios["R"], ratios["G"], ratios["B"]
            mix = [r * xyzs[0][i] + g * xyzs[1][i] + b * xyzs[2][i] for i in range(3)]
            xx, yy, zz = mix
            total = xx + yy + zz
            if total == 0:
                wx = wy = 0.0
            else:
                wx, wy = xx / total, yy / total

            from colorlab_pro.engines.gamut_calculator import xy_to_uv

            u, v = xy_to_uv(wx, wy)

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

            return {
                "red_xy": [round(red_xy[0], 4), round(red_xy[1], 4)],
                "green_xy": [round(green_xy[0], 4), round(green_xy[1], 4)],
                "blue_xy": [round(blue_xy[0], 4), round(blue_xy[1], 4)],
                "ratios": [round(ratios["R"], 4), round(ratios["G"], 4), round(ratios["B"], 4)],
                "white_xy": [round(wx, 4), round(wy, 4)],
                "white_uv": [round(u, 4), round(v, 4)],
                "cct": round(cct, 0),
                "results": results,
            }
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def whitepoint_calculate_ratios(self, payload: dict) -> dict:
        """Solve RGB mixing ratios to hit a target white point (xy)."""
        try:
            red_xy = validate_xy(payload["red_xy"], "red_xy")
            green_xy = validate_xy(payload["green_xy"], "green_xy")
            blue_xy = validate_xy(payload["blue_xy"], "blue_xy")
            target_xy = validate_xy(payload["target_xy"], "target_xy")

            def xy_to_xyz(x, y):
                if y == 0:
                    return [0.0, 0.0, 0.0]
                yy = 1.0
                xx = yy * x / y
                zz = yy * (1.0 - x - y) / y
                return [xx, yy, zz]

            matrix = [
                xy_to_xyz(*red_xy),
                xy_to_xyz(*green_xy),
                xy_to_xyz(*blue_xy),
            ]
            target_xyz = xy_to_xyz(*target_xy)

            coeffs, _residuals, _rank, _s = np.linalg.lstsq(
                np.array(matrix).T, np.array(target_xyz), rcond=None,
            )
            coeffs = np.maximum(coeffs, 0)
            total = float(np.sum(coeffs))
            if total == 0:
                ratios = {"R": 0.333, "G": 0.333, "B": 0.333}
            else:
                ratios = {
                    "R": round(float(coeffs[0]) / total, 4),
                    "G": round(float(coeffs[1]) / total, 4),
                    "B": round(float(coeffs[2]) / total, 4),
                }

            # Reuse whitepoint_calculate with the solved ratios
            calc_payload = {
                "red_xy": red_xy,
                "green_xy": green_xy,
                "blue_xy": blue_xy,
                "ratios": ratios,
            }
            result = self.whitepoint_calculate(calc_payload)
            result["ratios"] = [round(ratios["R"], 4), round(ratios["G"], 4), round(ratios["B"], 4)]
            return result
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    # -------------------------------------------------------------- #
    # Thickness Optimizer page methods
    # -------------------------------------------------------------- #

    def optimizer_get_initial_data(self) -> dict:
        """Return spectra list and empty optimization results."""
        try:
            summaries = self._spectrum_ctrl.list_spectra()
            spectra = [
                {
                    "id": s.id,
                    "name": s.name,
                    "category": s.category or "",
                    "channel": s.channel or "",
                }
                for s in summaries
            ]
            return {"spectra": spectra, "results": [], "best": None}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def optimizer_stop(self) -> None:
        """Request cancellation of the running optimization."""
        self._stop_event.set()

    def optimizer_optimize(self, payload: dict) -> dict:
        """Run a grid-search thickness optimization in a background thread.

        Returns immediately with a placeholder; the actual result is
        stored and can be polled.  For simplicity, we run synchronously
        here since pywebview's expose methods already run on a separate
        thread from the UI.
        """
        try:
            source_ids = [int(x) for x in payload["source_ids"]]
            cf_ids = [int(x) for x in payload["cf_ids"]]
            bounds = payload["bounds"]
            target_standard = payload.get("target_standard", "BT2020")
            target_xy = payload.get("target_xy")

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_ctrl.get_spectrum(sid) for sid in cf_ids]

            from colorlab_pro.dto.color import XY
            from colorlab_pro.engines.gamut_calculator import (
                build_gamut_from_primaries,
                coverage,
                match,
                standard_gamuts,
            )
            from colorlab_pro.engines.spectrum_analyzer import xy as spectrum_xy

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

            # Grid search
            steps = 10
            candidates: list[dict] = []
            total = steps ** 3
            count = 0
            self._stop_event.clear()
            for dr in np.linspace(bounds[0][0], bounds[0][1], steps):
                for dg in np.linspace(bounds[1][0], bounds[1][1], steps):
                    for db in np.linspace(bounds[2][0], bounds[2][1], steps):
                        count += 1
                        if self._stop_event.is_set():
                            return {"results": [], "best": None, "stopped": True}
                        # Yield to allow stop() to be processed
                        if count % 50 == 0:
                            time.sleep(0.001)
                        filtered = []
                        for src, alpha, d in zip(sources, alphas, [dr, dg, db], strict=False):
                            t = np.power(10.0, -alpha * d)
                            filtered.append(src.values * t)
                        white = Spectrum(
                            wavelengths=wavelengths, values=sum(filtered), unit=sources[0].unit,
                        )
                        white_xy = spectrum_xy(white)
                        delta = float(np.hypot(white_xy.x - target.x, white_xy.y - target.y))

                        primaries_xy = [
                            spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=sources[0].unit))
                            for v in filtered
                        ]
                        device = build_gamut_from_primaries(
                            "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
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

            candidates.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
            top = candidates[:5]
            for i, r in enumerate(top):
                r["rank"] = i + 1

            return {"results": top, "best": top[0] if top else None}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def optimizer_sensitivity_analysis(self, payload: dict) -> dict:
        """Vary one CF thickness at a time and return coverage / white point drift."""
        try:
            base = payload["base"]
            vary_channel = payload["vary_channel"]
            source_ids = [int(x) for x in payload["source_ids"]]
            cf_ids = [int(x) for x in payload["cf_ids"]]
            bounds = payload["bounds"]
            target_standard = payload.get("target_standard", "BT2020")

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_ctrl.get_spectrum(sid) for sid in cf_ids]

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
            try:
                target = standard_gamuts(target_standard)
            except (ValueError, KeyError):
                target = standard_gamuts("BT2020")
            channel_idx = {"R": 0, "G": 1, "B": 2}[vary_channel]
            lo, hi = bounds[channel_idx]

            points = []
            self._stop_event.clear()
            steps = 21
            for idx, d in enumerate(np.linspace(lo, hi, steps)):
                if self._stop_event.is_set():
                    break
                ds = [base[0], base[1], base[2]]
                ds[channel_idx] = d
                filtered = []
                for src, alpha, dd in zip(sources, alphas, ds, strict=False):
                    t = np.power(10.0, -alpha * dd)
                    filtered.append(src.values * t)
                primaries_xy = [
                    spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=sources[0].unit))
                    for v in filtered
                ]
                white = Spectrum(wavelengths=wavelengths, values=sum(filtered), unit=sources[0].unit)
                white_xy = spectrum_xy(white)
                device = build_gamut_from_primaries(
                    "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
                )
                cov = coverage(target, device)
                points.append({
                    "thickness": round(float(d), 3),
                    "coverage": round(float(cov), 1),
                    "white_x": round(float(white_xy.x), 4),
                    "white_y": round(float(white_xy.y), 4),
                })
            return {"channel": vary_channel, "points": points}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def optimizer_sensitivity_all(self, payload: dict) -> dict:
        """Run sensitivity for all 3 channels: vary each independently."""
        try:
            base = payload["base"]
            source_ids = [int(x) for x in payload["source_ids"]]
            cf_ids = [int(x) for x in payload["cf_ids"]]
            bounds = payload["bounds"]
            target_standard = payload.get("target_standard", "BT2020")

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_ctrl.get_spectrum(sid) for sid in cf_ids]

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
            try:
                target = standard_gamuts(target_standard)
            except (ValueError, KeyError):
                target = standard_gamuts("BT2020")

            steps = 21
            self._stop_event.clear()
            total = steps * 3
            count = 0
            results: dict[str, list[dict]] = {}
            for ch_name, ch_idx in [("R", 0), ("G", 1), ("B", 2)]:
                lo, hi = bounds[ch_idx]
                points = []
                for _, d in enumerate(np.linspace(lo, hi, steps)):
                    if self._stop_event.is_set():
                        break
                    count += 1
                    if count % 30 == 0:
                        time.sleep(0.001)
                    ds = [base[0], base[1], base[2]]
                    ds[ch_idx] = d
                    filtered = []
                    for src, alpha, dd in zip(sources, alphas, ds, strict=False):
                        t = np.power(10.0, -alpha * dd)
                        filtered.append(src.values * t)
                    primaries_xy = [
                        spectrum_xy(Spectrum(wavelengths=wavelengths, values=v, unit=sources[0].unit))
                        for v in filtered
                    ]
                    white = Spectrum(wavelengths=wavelengths, values=sum(filtered), unit=sources[0].unit)
                    white_xy = spectrum_xy(white)
                    device = build_gamut_from_primaries(
                        "Device", primaries_xy[0], primaries_xy[1], primaries_xy[2], white_xy,
                    )
                    cov = coverage(target, device)
                    points.append({
                        "thickness": round(float(d), 3),
                        "coverage": round(float(cov), 1),
                    })
                results[ch_name] = points

            return {"results": results, "base": base}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def optimizer_paste_spectrum(self, payload: dict) -> dict:
        """Parse clipboard text and save as a new spectrum (optimizer page version)."""
        try:
            text = payload.get("text", "")
            name = payload.get("name", "Pasted Spectrum")
            spectrum = parse_spectrum_from_text(text)
            if spectrum.meta is None:
                spectrum.meta = {}
            spectrum.meta["name"] = name
            sid = self._spectrum_ctrl.import_spectrum(spectrum, name=name, category="Pasted")
            if sid is None:
                return {"error": "Failed to import pasted spectrum"}
            return {"id": sid}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)
