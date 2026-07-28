"""Engines layer - pure computational algorithms (no I/O, no Qt)."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    # SpectrumNormalizer (T-02)
    "normalize",
    "interpolate",
    "auto_fill_gaps",
    "detect_channel",
    "CHANNEL_UNKNOWN",
    # SpectrumAnalyzer (T-03)
    "xyz",
    "xy",
    "uprime_vprime",
    "cct_mccamy",
    "dominant_wavelength",
    # ColorCalculator (T-04)
    "mix_spectra",
    "mix_xy",
    "mix_xyz",
    "luminance",
    "delta_uv",
    # GamutCalculator (T-05)
    "standard_gamuts",
    "build_gamut_from_primaries",
    "coverage",
    "match",
    "match_spectrum",
    "area",
    "contains",
    # WhitePointCalculator (T-06)
    "mixing_weights",
    "delta_xy_to_target",
    "nearest_white_point",
    # ThicknessOptimizer (T-06)
    "optimize_thickness",
    "CF_THICKNESS_BOUNDS_UM",
    # SpectrumManipulator (T-07)
    "translate_spectrum",
    "scale_fwhm",
    "peak_wavelength",
    "measure_fwhm",
    "compute_leakage_ratio",
    "separate_qd_spectrum",
    "recompose_qd_spectrum",
    "update_qd_blue_leakage",
    "adjust_qd_emission",
    "adjust_qd_full",
]

# Map of public names to (module_path, attribute_name).
# Lazy loading keeps import overhead low and avoids eagerly importing
# heavy dependencies such as numpy/scipy when only a subset of engines
# is needed.
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # SpectrumNormalizer (T-02)
    "normalize": ("colorlab_pro.engines.spectrum_normalizer", "normalize"),
    "interpolate": ("colorlab_pro.engines.spectrum_normalizer", "interpolate"),
    "auto_fill_gaps": ("colorlab_pro.engines.spectrum_normalizer", "auto_fill_gaps"),
    "detect_channel": ("colorlab_pro.engines.spectrum_normalizer", "detect_channel"),
    "CHANNEL_UNKNOWN": ("colorlab_pro.engines.spectrum_normalizer", "CHANNEL_UNKNOWN"),
    # SpectrumAnalyzer (T-03)
    "xyz": ("colorlab_pro.engines.spectrum_analyzer", "xyz"),
    "xy": ("colorlab_pro.engines.spectrum_analyzer", "xy"),
    "uprime_vprime": ("colorlab_pro.engines.spectrum_analyzer", "uprime_vprime"),
    "cct_mccamy": ("colorlab_pro.engines.spectrum_analyzer", "cct_mccamy"),
    "dominant_wavelength": ("colorlab_pro.engines.spectrum_analyzer", "dominant_wavelength"),
    # ColorCalculator (T-04)
    "mix_spectra": ("colorlab_pro.engines.color_calculator", "mix_spectra"),
    "mix_xy": ("colorlab_pro.engines.color_calculator", "mix_xy"),
    "mix_xyz": ("colorlab_pro.engines.color_calculator", "mix_xyz"),
    "luminance": ("colorlab_pro.engines.color_calculator", "luminance"),
    "delta_uv": ("colorlab_pro.engines.color_calculator", "delta_uv"),
    # GamutCalculator (T-05)
    "standard_gamuts": ("colorlab_pro.engines.gamut_calculator", "standard_gamuts"),
    "build_gamut_from_primaries": (
        "colorlab_pro.engines.gamut_calculator",
        "build_gamut_from_primaries",
    ),
    "coverage": ("colorlab_pro.engines.gamut_calculator", "coverage"),
    "match": ("colorlab_pro.engines.gamut_calculator", "match"),
    "match_spectrum": ("colorlab_pro.engines.gamut_calculator", "match_spectrum"),
    "area": ("colorlab_pro.engines.gamut_calculator", "area"),
    "contains": ("colorlab_pro.engines.gamut_calculator", "contains"),
    # WhitePointCalculator (T-06)
    "mixing_weights": ("colorlab_pro.engines.white_point_calculator", "mixing_weights"),
    "delta_xy_to_target": ("colorlab_pro.engines.white_point_calculator", "delta_xy_to_target"),
    "nearest_white_point": ("colorlab_pro.engines.white_point_calculator", "nearest_white_point"),
    # ThicknessOptimizer (T-06)
    "optimize_thickness": ("colorlab_pro.engines.thickness_optimizer", "optimize_thickness"),
    "CF_THICKNESS_BOUNDS_UM": (
        "colorlab_pro.engines.thickness_optimizer",
        "CF_THICKNESS_BOUNDS_UM",
    ),
    # SpectrumManipulator (T-07)
    "translate_spectrum": ("colorlab_pro.engines.spectrum_manipulator", "translate_spectrum"),
    "scale_fwhm": ("colorlab_pro.engines.spectrum_manipulator", "scale_fwhm"),
    "peak_wavelength": ("colorlab_pro.engines.spectrum_manipulator", "peak_wavelength"),
    "measure_fwhm": ("colorlab_pro.engines.spectrum_manipulator", "measure_fwhm"),
    "compute_leakage_ratio": ("colorlab_pro.engines.spectrum_manipulator", "compute_leakage_ratio"),
    "separate_qd_spectrum": ("colorlab_pro.engines.spectrum_manipulator", "separate_qd_spectrum"),
    "recompose_qd_spectrum": ("colorlab_pro.engines.spectrum_manipulator", "recompose_qd_spectrum"),
    "update_qd_blue_leakage": ("colorlab_pro.engines.spectrum_manipulator", "update_qd_blue_leakage"),
    "adjust_qd_emission": ("colorlab_pro.engines.spectrum_manipulator", "adjust_qd_emission"),
    "adjust_qd_full": ("colorlab_pro.engines.spectrum_manipulator", "adjust_qd_full"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
