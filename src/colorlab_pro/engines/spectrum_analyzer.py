"""SpectrumAnalyzer Engine.

Provides colorimetric analysis functions for a Spectrum:
- xyz(): CIE XYZ tristimulus
- xy(): CIE 1931 chromaticity
- uprime_vprime(): CIE 1976 u'v'
- cct_mccamy(): Correlated Color Temperature (Hernandez 1999)
- dominant_wavelength(): Wavelength of the dominant color
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from colorlab_pro.dto.color import XY, XYZ
from colorlab_pro.dto.spectrum import Spectrum

if TYPE_CHECKING:
    pass

# Cached colour-science singletons
_cmf_cache: dict[str, Any] = {}
_illuminant_sd_cache: dict[str, Any] = {}

# Supported observers / illuminants exposed to the UI.
OBSERVER_CHOICES = [
    "CIE 1931 2 Degree Standard Observer",
    "CIE 1964 10 Degree Standard Observer",
]

ILLUMINANT_CHOICES = [
    "A",
    "C",
    "D50",
    "D55",
    "D65",
    "D75",
    "E",
]


def _get_cmf(observer: str = "CIE 1931 2 Degree Standard Observer") -> Any:
    """Return the requested colour-science CMF (cached)."""
    import colour

    if observer not in _cmf_cache:
        if observer not in colour.MSDS_CMFS:
            raise ValueError(f"Unsupported observer: {observer!r}")
        _cmf_cache[observer] = colour.MSDS_CMFS[observer]
    return _cmf_cache[observer]


def _get_illuminant_sd(name: str = "D65") -> Any:
    """Return the requested illuminant spectral distribution (cached)."""
    import colour

    if name not in _illuminant_sd_cache:
        if name not in colour.SDS_ILLUMINANTS:
            raise ValueError(f"Unsupported illuminant: {name!r}")
        _illuminant_sd_cache[name] = colour.SDS_ILLUMINANTS[name]
    return _illuminant_sd_cache[name]


def _get_illuminant_xy(
    name: str = "D65", observer: str = "CIE 1931 2 Degree Standard Observer"
) -> XY:
    """Return the xy chromaticity of an illuminant for a given observer."""
    import colour

    if name in colour.CCS_ILLUMINANTS.get(observer, {}):
        xy_arr = colour.CCS_ILLUMINANTS[observer][name]
    elif name in colour.CCS_ILLUMINANTS.get("CIE 1931 2 Degree Standard Observer", {}):
        xy_arr = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"][name]
    else:
        raise ValueError(f"Unsupported illuminant: {name!r}")
    return XY(x=float(xy_arr[0]), y=float(xy_arr[1]))


def _to_spectral_distribution(spectrum: Spectrum) -> Any:
    """Convert a Spectrum to a colour-science SpectralDistribution."""
    import colour

    return colour.SpectralDistribution(spectrum.values, spectrum.wavelengths)


def xyz(
    spectrum: Spectrum,
    *,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> XYZ:
    """Compute CIE XYZ tristimulus values for a spectrum.

    Args:
        spectrum: Input spectrum.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        XYZ dataclass with X, Y, Z floats.
    """
    import colour

    sd = _to_spectral_distribution(spectrum)
    cmf = _get_cmf(observer)
    illuminant_sd = _get_illuminant_sd(illuminant)
    xyz_arr = colour.sd_to_XYZ(sd, cmf, illuminant=illuminant_sd)
    return XYZ(X=float(xyz_arr[0]), Y=float(xyz_arr[1]), Z=float(xyz_arr[2]))


def xy(
    spectrum: Spectrum,
    *,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> XY:
    """Compute CIE xy chromaticity coordinates.

    Args:
        spectrum: Input spectrum.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        XY dataclass.
    """
    import colour

    c = xyz(spectrum, observer=observer, illuminant=illuminant)
    xyz_arr = np.array([c.X, c.Y, c.Z], dtype=np.float64)
    xy_arr = colour.XYZ_to_xy(xyz_arr)
    return XY(x=float(xy_arr[0]), y=float(xy_arr[1]))


def uprime_vprime(
    spectrum: Spectrum,
    *,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> tuple[float, float]:
    """Compute CIE 1976 u'v' chromaticity coordinates via colour-science.

    Args:
        spectrum: Input spectrum.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        (u_prime, v_prime) tuple.
    """
    import colour

    c = xy(spectrum, observer=observer, illuminant=illuminant)
    uv = colour.xy_to_Luv_uv(np.array([c.x, c.y]))
    return (float(uv[0]), float(uv[1]))


def cct_mccamy(
    spectrum: Spectrum,
    *,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> float:
    """Compute Correlated Color Temperature (CCT).

    Uses the Hernandez 1999 approximation (a refinement of McCamy 1992)
    via colour-science's ``xy_to_CCT`` with method="Hernandez 1999".

    Args:
        spectrum: Input spectrum.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        CCT in Kelvin.
    """
    import colour

    c = xy(spectrum, observer=observer, illuminant=illuminant)
    return float(colour.temperature.xy_to_CCT(np.array([c.x, c.y]), method="Hernandez 1999"))


# Backwards-compatible alias; ``cct`` is the preferred name.
cct = cct_mccamy


def dominant_wavelength(
    spectrum: Spectrum,
    *,
    white: XY | None = None,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> float | None:
    """Compute the dominant wavelength of a spectrum.

    Args:
        spectrum: Input spectrum.
        white: Reference white point. Defaults to the selected illuminant.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        Dominant wavelength in nm, or None if it falls outside the spectrum locus.
    """
    if white is None:
        white = _get_illuminant_xy(illuminant, observer=observer)
    c = xy(spectrum, observer=observer, illuminant=illuminant)
    wavelengths = np.arange(380.0, 781.0, 1.0, dtype=np.float64)
    locus_xy = np.zeros((wavelengths.size, 2), dtype=np.float64)
    for i, wl in enumerate(wavelengths):
        v = np.zeros_like(wavelengths)
        idx = int(wl - 380.0)
        if 0 <= idx < v.size:
            v[idx] = 1.0
        s = Spectrum(wavelengths=wavelengths, values=v, unit="a.u.")
        c_i = xy(s, observer=observer, illuminant=illuminant)
        locus_xy[i, 0] = c_i.x
        locus_xy[i, 1] = c_i.y
    s_vec = np.array([c.x - white.x, c.y - white.y], dtype=np.float64)
    s_norm = np.linalg.norm(s_vec)
    if s_norm < 1e-12:
        return None
    s_hat = s_vec / s_norm
    diffs = locus_xy - np.array([white.x, white.y], dtype=np.float64)
    diffs_norm = np.linalg.norm(diffs, axis=1)
    diffs_hat = diffs / diffs_norm[:, None]
    cos_sim = diffs_hat @ s_hat
    best = int(np.argmax(cos_sim))
    if cos_sim[best] <= 0:
        return None
    return float(wavelengths[best])
