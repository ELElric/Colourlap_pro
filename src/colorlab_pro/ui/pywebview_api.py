"""pywebview API 桥接类.

将所有页面的 Backend 方法统一到一个类中，通过 pywebview 的 js_api 暴露给前端。

方法名前缀:
  spectrum_   — 光谱库页面
  gamut_      — 色域计算器页面
  whitepoint_ — 白点计算器页面
  optimizer_  — 膜厚优化页面
  history_    — 历史记录页面

pywebview 自动将 Python dict/list 序列化为 JSON，将 JSON 参数
反序列化为 Python dict/list，因此不需要手动 json.dumps / json.loads。
文件对话框使用 tkinter.filedialog 实现。
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
from colorlab_pro.dto.history import HistorySnapshot
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.exporters.report_exporter import ReportExporter
from colorlab_pro.services.history_service import HistoryService
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
        for w, v in zip(spectrum.wavelengths[::step], spectrum.values[::step], strict=True)
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

        # Create sub-controllers
        self._spectrum_ctrl = SpectrumController(main_ctrl)
        self._color_ctrl = ColorController(main_ctrl)
        self._opt_ctrl = OptimizationController(main_ctrl)

        # History service
        self._history_service = HistoryService(main_ctrl.session_factory)

        # Optimizer state
        self._opt_progress: int = 0
        self._opt_result: dict | None = None
        self._opt_running: bool = False
        self._current_stop_event: threading.Event | None = None
        self._opt_lock = threading.Lock()

        # Gamut page state
        self._last_primaries: list[dict] = [
            {"ch": "R", "x": 0.0, "y": 0.0},
            {"ch": "G", "x": 0.0, "y": 0.0},
            {"ch": "B", "x": 0.0, "y": 0.0},
        ]
        self._last_results: list[dict] = []

        # pywebview window reference (set after window creation)
        self._window: Any = None

        # Settings (theme, window state, password)
        self._settings: dict[str, Any] = {}
        self._load_settings()

    # -------------------------------------------------------------- #
    # Window / Settings / Cross-page communication
    # -------------------------------------------------------------- #

    _SETTINGS_FILE = Path.home() / ".colorlab_pro" / "settings.json"

    def _load_settings(self) -> None:
        """Load settings from JSON file."""
        try:
            if self._SETTINGS_FILE.exists():
                import json

                self._settings = json.loads(self._SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            self._settings = {}

    def _save_settings(self) -> None:
        """Persist settings to JSON file."""
        try:
            self._SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            import json

            self._SETTINGS_FILE.write_text(
                json.dumps(self._settings, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    def set_window(self, window: Any) -> None:
        """Set the pywebview window reference for JS evaluation (progress push)."""
        self._window = window

    def _push_js(self, js_code: str) -> None:
        """Evaluate JavaScript in the pywebview window (fire-and-forget)."""
        if self._window is not None:
            try:
                self._window.evaluate_js(js_code)
            except Exception:  # noqa: BLE001
                pass

    # --- Theme --- #

    def get_theme(self) -> str:
        """Return current theme ('dark' or 'light')."""
        return self._settings.get("theme", "dark")

    def set_theme(self, theme: str) -> dict:
        """Persist and broadcast theme change."""
        self._settings["theme"] = theme
        self._save_settings()
        self._push_js(f"window.applyTheme && window.applyTheme('{theme}')")
        return {"theme": theme}

    # --- Window state --- #

    def get_window_state(self) -> dict:
        """Return saved window geometry."""
        return self._settings.get("window", {})

    def save_window_state(self, payload: dict) -> dict:
        """Persist window geometry."""
        self._settings["window"] = payload
        self._save_settings()
        return {"ok": True}

    def set_window_title(self, title: str) -> None:
        """Update the native window title."""
        if self._window is not None:
            try:
                self._window.set_title(f"ColorLab Pro — {title}")
            except Exception:  # noqa: BLE001
                pass

    # --- Password protection --- #

    def verify_password(self, password: str) -> dict:
        """Verify the application password.

        Returns {ok: bool, first_run: bool}.
        On first run (no password set), any non-empty password becomes the new password.
        """
        stored = self._settings.get("password_hash")
        if not stored:
            # First run — accept and store the password
            if password and len(password) >= 4:
                import hashlib

                self._settings["password_hash"] = hashlib.sha256(
                    password.encode()
                ).hexdigest()
                self._save_settings()
                return {"ok": True, "first_run": True}
            return {"ok": False, "first_run": True, "error": "Password too short (min 4 chars)"}

        import hashlib

        entered = hashlib.sha256(password.encode()).hexdigest()
        return {"ok": entered == stored, "first_run": False}

    def is_password_set(self) -> dict:
        """Check whether a password has been configured."""
        return {"password_required": bool(self._settings.get("password_hash"))}

    # --- Cross-page communication --- #

    def gamut_get_primaries(self) -> dict:
        """Return the last computed RGB primaries from the Gamut Calculator page.

        Called by the White Point page to import RGB coordinates.
        """
        return {
            "primaries": self._last_primaries,
            "has_data": any(p["x"] != 0.0 or p["y"] != 0.0 for p in self._last_primaries),
        }

    def whitepoint_get_gamut_primaries(self) -> dict:
        """Return gamut primaries formatted for the White Point page.

        Returns red_xy / green_xy / blue_xy arrays, or null if no data.
        """
        if not any(p["x"] != 0.0 or p["y"] != 0.0 for p in self._last_primaries):
            return {"has_data": False}
        r = self._last_primaries[0]
        g = self._last_primaries[1]
        b = self._last_primaries[2]
        return {
            "has_data": True,
            "red_xy": [r["x"], r["y"]],
            "green_xy": [g["x"], g["y"]],
            "blue_xy": [b["x"], b["y"]],
        }

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

    def _default_selections(self) -> dict:
        """Return default spectrum IDs by matching known names.

        RGB sources: QD-R, QD-G, B-LED
        CF spectra:  R110B-2, BD1-SC1000G, B150B-2
        """
        defaults: dict[str, int | None] = {
            "red": None, "green": None, "blue": None,
            "cf_red": None, "cf_green": None, "cf_blue": None,
        }
        name_map = {
            "red":     [("QD-R", "QD_RED", "QD-RED"), ("cat", "QD", "ch", "R")],
            "green":   [("QD-G", "QD_GREEN", "QD-GREEN"), ("cat", "QD", "ch", "G")],
            "blue":    [("B-LED", "BLED", "B-LED", "LED-B"), ("cat", "LED", "ch", "B"), ("cat", "QD", "ch", "B")],
            "cf_red":  [("R110B-2", "R110B2"), ("cat", "CF", "ch", "R")],
            "cf_green":[("BD1-SC1000G", "BD1SC1000G"), ("cat", "CF", "ch", "G")],
            "cf_blue": [("B150B-2", "B150B2"), ("cat", "CF", "ch", "B")],
        }
        try:
            summaries = self._spectrum_ctrl.list_spectra()
        except Exception:  # noqa: BLE001
            return defaults

        for key, matchers in name_map.items():
            names = matchers[0]
            fallbacks = matchers[1:]
            names_upper = [n.upper() for n in names]
            for s in summaries:
                sname = (s.name or "").upper().strip()
                if sname in names_upper:
                    defaults[key] = s.id
                    break
            if defaults[key] is None:
                for s in summaries:
                    cat = (s.category or "").upper()
                    ch = (s.channel or "").upper()
                    for fb in fallbacks:
                        if cat == fb[1] and ch == fb[3]:
                            defaults[key] = s.id
                            break
                    if defaults[key] is not None:
                        break
        return defaults

    def gamut_get_initial_data(self) -> dict:
        """Return spectra list, default selections, and empty gamut results."""
        try:
            return {
                "spectra": self._gamut_spectra_json(),
                "results": [],
                "defaults": self._default_selections(),
            }
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def _apply_cf_filter(
        self,
        spectrum: Spectrum,
        cf_spectrum: Spectrum | None,
        thickness: float,
    ) -> Spectrum:
        """Apply Color Filter + thickness (Lambert-Beer) to a spectrum.

        If the CF spectrum carries a ``thickness_um`` in its metadata (the
        physical thickness at which the transmittance data was measured),
        the transmittance is first normalised to unit-thickness before
        applying the requested *thickness*.  This ensures correct results
        regardless of the measurement thickness.
        """
        if cf_spectrum is None:
            return spectrum
        wl = spectrum.wavelengths
        cf_wl = cf_spectrum.wavelengths
        cf_val = cf_spectrum.values
        t = np.interp(wl, cf_wl, cf_val, left=1.0, right=1.0)
        t = np.where(t > 1.5, t / 100.0, t)
        t = np.clip(t, 1e-6, 1.0)
        # Normalise CF transmittance to unit thickness if measurement
        # thickness is recorded in metadata.
        measured_thickness = cf_spectrum.meta.get("thickness_um") if cf_spectrum.meta else None
        if measured_thickness is not None and measured_thickness > 0 and thickness > 0:
            t_unit = np.power(t, 1.0 / measured_thickness)
            attenuation = np.power(t_unit, thickness)
        else:
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
                import colour
                xyz = colour.xy_to_XYZ(np.array([x, y]))
                return (float(xyz[0]), float(xyz[1]), float(xyz[2]))

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
                    # FWHM: 使用线性插值法精确计算半高宽
                    half_max = peak_val / 2.0
                    above_half = sp.values >= half_max
                    if np.any(above_half):
                        indices = np.where(above_half)[0]
                        # 左边界插值
                        left_idx = indices[0]
                        if left_idx > 0 and sp.values[left_idx - 1] < half_max:
                            frac_l = (half_max - sp.values[left_idx - 1]) / (
                                sp.values[left_idx] - sp.values[left_idx - 1]
                            )
                            left_wl = sp.wavelengths[left_idx - 1] + frac_l * (
                                sp.wavelengths[left_idx] - sp.wavelengths[left_idx - 1]
                            )
                        else:
                            left_wl = sp.wavelengths[left_idx]
                        # 右边界插值
                        right_idx = indices[-1]
                        if right_idx < len(sp.values) - 1 and sp.values[right_idx + 1] < half_max:
                            frac_r = (half_max - sp.values[right_idx + 1]) / (
                                sp.values[right_idx] - sp.values[right_idx + 1]
                            )
                            right_wl = sp.wavelengths[right_idx + 1] - frac_r * (
                                sp.wavelengths[right_idx + 1] - sp.wavelengths[right_idx]
                            )
                        else:
                            right_wl = sp.wavelengths[right_idx]
                        fwhm_nm = round(float(right_wl - left_wl), 1)
                    else:
                        fwhm_nm = None
                except Exception:
                    peak_nm, fwhm_nm = None, None
                try:
                    import colour

                    # 主波长: 使用 colour-science 的 dominant_wavelength (光谱轨迹交叉法)
                    xy_arr = np.array([x, y])
                    xy_n = np.array([0.3127, 0.3290])
                    dw_result = colour.dominant_wavelength(xy_arr, xy_n)
                    dw_wl = float(dw_result[0])
                    dominant_nm = int(round(dw_wl)) if dw_wl > 0 else None
                    # 色纯度: 使用 dominant_wavelength 返回的光谱轨迹交点精确计算
                    try:
                        xy_wl = dw_result[1]
                        dist_cw = math.sqrt((x - xy_n[0]) ** 2 + (y - xy_n[1]) ** 2)
                        dist_lw = math.sqrt(
                            (float(xy_wl[0]) - xy_n[0]) ** 2 + (float(xy_wl[1]) - xy_n[1]) ** 2
                        )
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
                        "spectrum_name": (
                            (cast(Spectrum, specs[idx]).meta.get("name", "") if specs[idx].meta else "")
                            if mode == "rgbcf" and specs and specs[idx]
                            else (cast(Spectrum, white_spec).meta.get("name", "") if white_spec and white_spec.meta else "")
                        ),
                        "cf_name": (cf_specs[idx].meta.get("name", "") if cf_specs[idx] and cf_specs[idx].meta else None) if cf_specs[idx] else None,
                        "cf_thickness": thicknesses[idx] if thicknesses[idx] > 0 else None,
                    }
                )
            self._last_primaries = primaries

            results = []
            for std in ["sRGB", "NTSC", "DCI-P3", "Adobe RGB", "BT2020"]:
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
        import colour
        import numpy as np

        xyz = colour.xy_to_XYZ(np.array([x, y]))
        return float(xyz[0]), float(xyz[1]), float(xyz[2])

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
                import colour
                xyz = colour.xy_to_XYZ(np.array([x, y]))
                return [float(xyz[0]), float(xyz[1]), float(xyz[2])]

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
        """Return spectra list, default selections, and empty optimization results."""
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
            return {
                "spectra": spectra,
                "results": [],
                "best": None,
                "defaults": self._default_selections(),
            }
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def optimizer_stop(self) -> None:
        """Request cancellation of the running optimization."""
        with self._opt_lock:
            if self._current_stop_event:
                self._current_stop_event.set()

    def optimizer_optimize(self, payload: dict) -> dict:
        """Start a grid-search thickness optimization in a background thread.

        Returns immediately with {started: True}.  Progress is pushed to the
        frontend via window.evaluate_js calls to ``window.updateOptProgress``
        and the final result via ``window.updateOptResult``.
        """
        stop_event = threading.Event()
        with self._opt_lock:
            if self._opt_running:
                return {"error": "Optimization already running"}
            self._opt_running = True
            self._current_stop_event = stop_event
        self._opt_progress = 0
        self._opt_result = None

        thread = threading.Thread(
            target=self._optimize_worker, args=(payload, stop_event), daemon=True
        )
        thread.start()
        return {"started": True}

    def _optimize_worker(self, payload: dict, stop_event: threading.Event) -> None:
        """Background worker: runs the grid search and pushes progress/result."""
        import json as _json

        try:
            source_ids = [int(x) for x in payload["source_ids"]]
            cf_ids = [int(x) for x in payload["cf_ids"]]
            bounds = payload["bounds"]
            target_standard = payload.get("target_standard", "BT2020")
            target_xy = payload.get("target_xy")

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_ctrl.get_spectrum(sid) for sid in cf_ids]

            from colorlab_pro.dto.color import XY
            from colorlab_pro.engines.gamut_calculator import standard_gamuts
            from colorlab_pro.engines.thickness_optimizer import (
                _compute_single_candidate,
                _prepare_grid_inputs,
            )

            wavelengths, src_vals, alphas, unit = _prepare_grid_inputs(sources, cfs)

            if target_xy is not None:
                target = XY(float(target_xy[0]), float(target_xy[1]))
            else:
                wp = standard_gamuts(target_standard).white
                target = XY(wp[0], wp[1])

            target_gamut = standard_gamuts(target_standard)

            # Grid search
            steps = 10
            candidates: list[dict] = []
            total = steps ** 3
            count = 0
            for dr in np.linspace(bounds[0][0], bounds[0][1], steps):
                for dg in np.linspace(bounds[1][0], bounds[1][1], steps):
                    for db in np.linspace(bounds[2][0], bounds[2][1], steps):
                        count += 1
                        if stop_event.is_set():
                            self._push_js("window.updateOptProgress && window.updateOptProgress(0, 'Stopped')")
                            self._push_js(
                                "window.updateOptResult && window.updateOptResult("
                                + _json.dumps({"results": [], "best": None, "stopped": True})
                                + ")"
                            )
                            return
                        # Push progress every 5%
                        if count % 50 == 0:
                            pct = int(100 * count / total)
                            self._opt_progress = pct
                            self._push_js(
                                f"window.updateOptProgress && window.updateOptProgress({pct}, 'Running grid search...')"
                            )
                        candidates.append(
                            _compute_single_candidate(
                                wavelengths, src_vals, alphas,
                                [dr, dg, db], target, target_gamut, unit,
                            )
                        )

            candidates.sort(key=lambda x: (x["delta_xy"], -x["coverage"]))
            top = candidates[:5]
            for i, r in enumerate(top):
                r["rank"] = i + 1

            result = {"results": top, "best": top[0] if top else None}
            self._opt_result = result
            self._opt_progress = 100
            best_cov = top[0]["coverage"] if top else 0
            self._push_js(
                f"window.updateOptProgress && window.updateOptProgress(100, 'Best coverage: {best_cov:.1f}%')"
            )
            self._push_js(
                "window.updateOptResult && window.updateOptResult(" + _json.dumps(result) + ")"
            )
        except Exception as exc:  # noqa: BLE001
            err = _safe_error(exc)
            self._opt_result = err
            self._push_js(
                "window.updateOptResult && window.updateOptResult(" + _json.dumps(err) + ")"
            )
        finally:
            with self._opt_lock:
                self._opt_running = False
                self._current_stop_event = None

    def optimizer_get_progress(self) -> dict:
        """Return current optimization progress (fallback polling)."""
        return {
            "running": self._opt_running,
            "progress": self._opt_progress,
            "result": self._opt_result,
        }

    def optimizer_sensitivity_analysis(self, payload: dict) -> dict:
        """Vary one CF thickness at a time and return coverage / white point drift."""
        try:
            base = payload["base"]
            vary_channel = payload["vary_channel"]
            source_ids = [int(x) for x in payload["source_ids"]]
            cf_ids = [int(x) for x in payload["cf_ids"]]
            bounds = payload["bounds"]
            target_standard = payload.get("target_standard", "BT2020")
            target_xy = payload.get("target_xy")

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_ctrl.get_spectrum(sid) for sid in cf_ids]

            from colorlab_pro.dto.color import XY
            from colorlab_pro.engines.gamut_calculator import standard_gamuts
            from colorlab_pro.engines.thickness_optimizer import sensitivity_analysis

            if target_xy is not None:
                target = XY(float(target_xy[0]), float(target_xy[1]))
            else:
                wp = standard_gamuts(target_standard).white
                target = XY(wp[0], wp[1])

            channel_idx = {"R": 0, "G": 1, "B": 2}[vary_channel]
            stop_event = threading.Event()

            points = sensitivity_analysis(
                sources, cfs, bounds, base, channel_idx, target,
                target_standard=target_standard, steps=21,
                progress_callback=lambda pct: self._push_js(
                    f"window.updateProgress && window.updateProgress({pct})"
                ),
                cancel_check=lambda: stop_event.is_set(),
            )
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
            target_xy = payload.get("target_xy")

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_ctrl.get_spectrum(sid) for sid in cf_ids]

            from colorlab_pro.dto.color import XY
            from colorlab_pro.engines.gamut_calculator import standard_gamuts
            from colorlab_pro.engines.thickness_optimizer import sensitivity_all_channels

            if target_xy is not None:
                target = XY(float(target_xy[0]), float(target_xy[1]))
            else:
                wp = standard_gamuts(target_standard).white
                target = XY(wp[0], wp[1])

            stop_event = threading.Event()

            results = sensitivity_all_channels(
                sources, cfs, bounds, base, target,
                target_standard=target_standard, steps=21,
                progress_callback=lambda pct: self._push_js(
                    f"window.updateProgress && window.updateProgress({pct})"
                ),
                cancel_check=lambda: stop_event.is_set(),
            )
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

    # ------------------------------------------------------------------ #
    # Filter 2: CF material selection
    # ------------------------------------------------------------------ #

    def optimizer_select_cf_materials(self, payload: dict) -> dict:
        """Start CF material selection in a background thread.

        Payload keys:
            source_ids: [R, G, B] source spectrum IDs.
            cf_library: {"R": [id, ...], "G": [id, ...], "B": [id, ...]}
            thicknesses: [R, G, B] fixed thicknesses in μm.
            target_standard: e.g. "BT2020".
            target_xy: optional [x, y].

        Returns {started: True} immediately; progress and results are
        pushed via window.updateCFMaterialsProgress / .updateCFMaterialsResult.
        """
        stop_event = threading.Event()
        with self._opt_lock:
            if self._opt_running:
                return {"error": "Another optimization is running"}
            self._opt_running = True
            self._current_stop_event = stop_event
        self._opt_progress = 0

        thread = threading.Thread(
            target=self._cf_materials_worker, args=(payload, stop_event), daemon=True
        )
        thread.start()
        return {"started": True}

    def _cf_materials_worker(self, payload: dict, stop_event: threading.Event) -> None:
        """Background worker for CF material selection."""
        import json as _json

        try:
            source_ids = [int(x) for x in payload["source_ids"]]
            cf_id_library = payload["cf_library"]
            thicknesses = payload["thicknesses"]
            target_standard = payload.get("target_standard", "BT2020")
            target_xy = payload.get("target_xy")

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]

            # Build CF library from spectrum IDs.
            cf_library: dict[str, list[Spectrum]] = {}
            for ch, ids in cf_id_library.items():
                cf_library[ch] = [
                    self._spectrum_ctrl.get_spectrum(int(i)) for i in ids
                ]

            from colorlab_pro.dto.color import XY
            from colorlab_pro.engines.gamut_calculator import standard_gamuts
            from colorlab_pro.engines.thickness_optimizer import select_cf_materials

            if target_xy is not None:
                target = XY(float(target_xy[0]), float(target_xy[1]))
            else:
                wp = standard_gamuts(target_standard).white
                target = XY(wp[0], wp[1])

            def _cf_progress_cb(pct):
                self._opt_progress = pct
                self._push_js(
                    f"window.updateCFMaterialsProgress && window.updateCFMaterialsProgress({pct})"
                )

            results = select_cf_materials(
                sources, cf_library, thicknesses, target,
                target_standard=target_standard,
                progress_callback=_cf_progress_cb,
                cancel_check=lambda: stop_event.is_set(),
            )

            result = {"results": results, "best": results[0] if results else None}
            self._opt_result = result
            self._opt_progress = 100
            self._push_js(
                "window.updateCFMaterialsResult && window.updateCFMaterialsResult("
                + _json.dumps(result) + ")"
            )
        except Exception as exc:  # noqa: BLE001
            err = _safe_error(exc)
            self._opt_result = err
            self._push_js(
                "window.updateCFMaterialsResult && window.updateCFMaterialsResult("
                + _json.dumps(err) + ")"
            )
        finally:
            with self._opt_lock:
                self._opt_running = False
                self._current_stop_event = None

    # ------------------------------------------------------------------ #
    # Filter 3: Emission spectrum optimization
    # ------------------------------------------------------------------ #

    def optimizer_optimize_emission(self, payload: dict) -> dict:
        """Start emission spectrum optimization in a background thread.

        Payload keys:
            source_ids: [R, G, B] source spectrum IDs.
            cf_ids: [RCF, GCF, BCF] spectrum IDs.
            thicknesses: [R, G, B] fixed thicknesses in μm.
            target_standard: e.g. "BT2020".
            target_xy: optional [x, y].
            peak_ranges: optional [[min, max] × 3] peak shift ranges in nm.
            fwhm_ranges: optional [[min, max] × 3] FWHM factor ranges.
            is_qd: optional [bool × 3] QD flags.
            blue_cutoff: optional float, default 500.0.
            steps: optional int, default 5.

        Returns {started: True} immediately; progress and results are
        pushed via window.updateEmissionProgress / .updateEmissionResult.
        """
        stop_event = threading.Event()
        with self._opt_lock:
            if self._opt_running:
                return {"error": "Another optimization is running"}
            self._opt_running = True
            self._current_stop_event = stop_event
        self._opt_progress = 0

        thread = threading.Thread(
            target=self._emission_worker, args=(payload, stop_event), daemon=True
        )
        thread.start()
        return {"started": True}

    def _emission_worker(self, payload: dict, stop_event: threading.Event) -> None:
        """Background worker for emission spectrum optimization."""
        import json as _json

        try:
            source_ids = [int(x) for x in payload["source_ids"]]
            cf_ids = [int(x) for x in payload["cf_ids"]]
            thicknesses = payload["thicknesses"]
            target_standard = payload.get("target_standard", "BT2020")
            target_xy = payload.get("target_xy")
            peak_ranges = payload.get("peak_ranges")
            fwhm_ranges = payload.get("fwhm_ranges")
            is_qd = payload.get("is_qd")
            blue_cutoff = payload.get("blue_cutoff", 500.0)
            steps = payload.get("steps", 5)

            sources = [self._spectrum_ctrl.get_spectrum(sid) for sid in source_ids]
            cfs = [self._spectrum_ctrl.get_spectrum(sid) for sid in cf_ids]

            from colorlab_pro.dto.color import XY
            from colorlab_pro.engines.gamut_calculator import standard_gamuts
            from colorlab_pro.engines.thickness_optimizer import optimize_emission_spectra

            if target_xy is not None:
                target = XY(float(target_xy[0]), float(target_xy[1]))
            else:
                wp = standard_gamuts(target_standard).white
                target = XY(wp[0], wp[1])

            # Convert lists to tuples for engine.
            if peak_ranges:
                peak_ranges = [tuple(r) for r in peak_ranges]
            if fwhm_ranges:
                fwhm_ranges = [tuple(r) for r in fwhm_ranges]

            def _em_progress_cb(pct):
                self._opt_progress = pct
                self._push_js(
                    f"window.updateEmissionProgress && window.updateEmissionProgress({pct})"
                )

            results = optimize_emission_spectra(
                sources, cfs, thicknesses, target,
                target_standard=target_standard,
                peak_ranges=peak_ranges,
                fwhm_ranges=fwhm_ranges,
                is_qd=is_qd,
                blue_cutoff=blue_cutoff,
                steps=steps,
                progress_callback=_em_progress_cb,
                cancel_check=lambda: stop_event.is_set(),
            )

            result = {"results": results, "best": results[0] if results else None}
            self._opt_result = result
            self._opt_progress = 100
            self._push_js(
                "window.updateEmissionResult && window.updateEmissionResult("
                + _json.dumps(result) + ")"
            )
        except Exception as exc:  # noqa: BLE001
            err = _safe_error(exc)
            self._opt_result = err
            self._push_js(
                "window.updateEmissionResult && window.updateEmissionResult("
                + _json.dumps(err) + ")"
            )
        finally:
            with self._opt_lock:
                self._opt_running = False
                self._current_stop_event = None

    # ------------------------------------------------------------------ #
    # Spectrum preview (for Filter 3 preview before optimization)
    # ------------------------------------------------------------------ #

    def optimizer_preview_spectrum_adjust(
        self, payload: dict
    ) -> dict:
        """Preview a single spectrum adjustment and return sampled data.

        Payload keys:
            spectrum_id: int
            peak_delta: float (nm)
            fwhm_factor: float
            is_qd: bool
            b_led_id: int (required if is_qd)
            new_b_led_id: int (optional, if B-LED also adjusted)
            new_b_led_peak_delta: float
            new_b_led_fwhm_factor: float
            blue_cutoff: float (default 500.0)

        Returns:
            {"data": [[wl, val], ...], "peak_nm": float, "fwhm_nm": float}
        """
        try:
            from colorlab_pro.engines.spectrum_manipulator import (
                adjust_qd_emission,
                adjust_qd_full,
                measure_fwhm,
                peak_wavelength,
                scale_fwhm,
                translate_spectrum,
            )

            sid = int(payload["spectrum_id"])
            peak_delta = float(payload.get("peak_delta", 0.0))
            fwhm_factor = float(payload.get("fwhm_factor", 1.0))
            is_qd = bool(payload.get("is_qd", False))
            blue_cutoff = float(payload.get("blue_cutoff", 500.0))

            spec = self._spectrum_ctrl.get_spectrum(sid)
            if spec is None:
                return {"error": "Spectrum not found"}

            if not is_qd:
                adjusted = spec
                if abs(peak_delta) > 1e-6:
                    adjusted = translate_spectrum(adjusted, peak_delta)
                if abs(fwhm_factor - 1.0) > 1e-6:
                    adjusted = scale_fwhm(adjusted, fwhm_factor)
            else:
                b_led_id = payload.get("b_led_id")
                if b_led_id is None:
                    return {"error": "b_led_id is required for QD spectra"}
                b_led = self._spectrum_ctrl.get_spectrum(int(b_led_id))
                if b_led is None:
                    return {"error": "B-LED spectrum not found"}

                new_b_led_id = payload.get("new_b_led_id")
                if new_b_led_id is not None:
                    new_b_led = self._spectrum_ctrl.get_spectrum(int(new_b_led_id))
                    if new_b_led is None:
                        return {"error": "New B-LED spectrum not found"}
                    new_b_led_peak_delta = float(payload.get("new_b_led_peak_delta", 0.0))
                    new_b_led_fwhm_factor = float(payload.get("new_b_led_fwhm_factor", 1.0))
                    adj_b_led = new_b_led
                    if abs(new_b_led_peak_delta) > 1e-6:
                        adj_b_led = translate_spectrum(adj_b_led, new_b_led_peak_delta)
                    if abs(new_b_led_fwhm_factor - 1.0) > 1e-6:
                        adj_b_led = scale_fwhm(adj_b_led, new_b_led_fwhm_factor)
                    adjusted = adjust_qd_full(
                        spec, b_led, adj_b_led,
                        peak_delta=peak_delta,
                        fwhm_factor=fwhm_factor,
                        blue_cutoff=blue_cutoff,
                    )
                else:
                    adjusted = adjust_qd_emission(
                        spec, b_led,
                        peak_delta=peak_delta,
                        fwhm_factor=fwhm_factor,
                        blue_cutoff=blue_cutoff,
                    )

            def _sig2(v: float) -> float:
                if v == 0:
                    return 0.0
                decimals = 5 - int(math.floor(math.log10(abs(v))))
                return round(v, max(decimals, 0))

            return {
                "original_wavelengths": [round(float(w), 1) for w in spec.wavelengths[::5]],
                "original_values": [_sig2(float(v)) for v in spec.values[::5]],
                "adjusted_wavelengths": [round(float(w), 1) for w in adjusted.wavelengths[::5]],
                "adjusted_values": [_sig2(float(v)) for v in adjusted.values[::5]],
                "peak_nm": round(peak_wavelength(adjusted), 1),
                "fwhm_nm": round(measure_fwhm(adjusted), 1),
            }
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    # -------------------------------------------------------------- #
    # History page methods
    # -------------------------------------------------------------- #

    def history_save(self, payload: dict) -> dict:
        """Save a calculation snapshot to history.

        Payload keys:
            name, mode, channels (list of channel dicts),
            gamut_results (list of gamut dicts),
            target_xy_x, target_xy_y, achieved_xy_x, achieved_xy_y,
            optimized_thickness_json, delta_xy, meta (dict)
        """
        try:
            from colorlab_pro.dto.history import ChannelSnapshot, GamutSnapshot

            channels = tuple(
                ChannelSnapshot(**ch) for ch in payload.get("channels", [])
            )
            gamut_results = tuple(
                GamutSnapshot(**g) for g in payload.get("gamut_results", [])
            )
            snapshot = HistorySnapshot(
                name=payload.get("name", ""),
                mode=payload.get("mode", ""),
                channels=channels,
                gamut_results=gamut_results,
                target_xy_x=payload.get("target_xy_x"),
                target_xy_y=payload.get("target_xy_y"),
                achieved_xy_x=payload.get("achieved_xy_x"),
                achieved_xy_y=payload.get("achieved_xy_y"),
                optimized_thickness_json=payload.get("optimized_thickness_json"),
                delta_xy=payload.get("delta_xy"),
                project_id=payload.get("project_id"),
                meta=payload.get("meta", {}),
            )
            record_id = self._history_service.save_snapshot(snapshot)
            return {"ok": True, "id": record_id}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def history_list(self, payload: dict | None = None) -> list[dict] | dict:
        """List history records, newest first. Returns summary dicts for the table."""
        try:
            project_id = None
            limit = 100
            if payload:
                project_id = payload.get("project_id")
                limit = payload.get("limit", 100)
            snapshots = self._history_service.list_snapshots(
                project_id=project_id, limit=limit
            )
            results = []
            for s in snapshots:
                results.append(
                    {
                        "id": s.meta.get("db_id", 0) if s.meta else 0,
                        "name": s.name,
                        "mode": s.mode,
                        "created_at": s.meta.get("created_at", "") if s.meta else "",
                        "channel_count": len(s.channels),
                        "has_gamut": len(s.gamut_results) > 0,
                        "has_optimization": (
                            s.target_xy_x is not None or s.optimized_thickness_json is not None
                        ),
                    }
                )
            return results
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def history_load(self, payload: dict) -> dict:
        """Load a history record by ID and return full detail data."""
        try:
            history_id = int(payload["id"])
            snapshot = self._history_service.load_snapshot(history_id)
            if snapshot is None:
                return {"ok": False, "error": "History record not found"}

            channels = []
            for ch in snapshot.channels:
                channels.append(
                    {
                        "name": ch.name,
                        "spectrum_name": ch.spectrum_name,
                        "xy": [ch.xy_x, ch.xy_y],
                        "uv": [ch.uv_u, ch.uv_v],
                        "peak_wavelength": ch.peak_wavelength,
                        "fwhm": ch.fwhm,
                        "dominant_wavelength": ch.dominant_wavelength,
                        "purity": ch.purity,
                        "cf_name": ch.cf_name,
                        "cf_thickness_um": ch.cf_thickness_um,
                    }
                )

            gamut_results = []
            for g in snapshot.gamut_results:
                gamut_results.append(
                    {
                        "standard_name": g.standard_name,
                        "coverage_1931": g.coverage_1931,
                        "coverage_1976": g.coverage_1976,
                        "match_1931": g.match_1931,
                        "match_1976": g.match_1976,
                    }
                )

            result: dict[str, Any] = {
                "ok": True,
                "id": history_id,
                "name": snapshot.name,
                "mode": snapshot.mode,
                "created_at": snapshot.meta.get("created_at", "") if snapshot.meta else "",
                "channels": channels,
                "gamut_results": gamut_results,
            }

            if snapshot.target_xy_x is not None and snapshot.target_xy_y is not None:
                result["target_xy"] = [snapshot.target_xy_x, snapshot.target_xy_y]
            if snapshot.achieved_xy_x is not None and snapshot.achieved_xy_y is not None:
                result["achieved_xy"] = [snapshot.achieved_xy_x, snapshot.achieved_xy_y]
            if snapshot.delta_xy is not None:
                result["delta_xy"] = snapshot.delta_xy
            if snapshot.optimized_thickness_json:
                import json as _json

                result["optimized_thickness"] = _json.loads(snapshot.optimized_thickness_json)

            return result
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def history_rename(self, payload: dict) -> dict:
        """Rename a history record."""
        try:
            history_id = int(payload["id"])
            new_name = str(payload["name"])
            ok = self._history_service.rename(history_id, new_name)
            return {"ok": ok}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    def history_delete(self, payload: dict) -> dict:
        """Delete a history record."""
        try:
            history_id = int(payload["id"])
            ok = self._history_service.delete(history_id)
            return {"ok": ok}
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)

    # ================================================================== #
    # Reference Data Page
    # ================================================================== #

    def reference_get_data(self) -> dict:
        """Return all reference data for the reference page."""
        try:
            from colorlab_pro.engines.reference_data import get_reference_data

            return get_reference_data()
        except Exception as exc:  # noqa: BLE001
            return _safe_error(exc)
