"""SpectrumAnalyzer Engine.

Provides colorimetric analysis functions for a Spectrum:
- xyz(): CIE XYZ tristimulus
- xy(): CIE 1931 chromaticity
- uprime_vprime(): CIE 1976 u'v'
- cct_mccamy(): Correlated Color Temperature (Hernandez 1999)
- dominant_wavelength(): Wavelength of the dominant color
"""

from __future__ import annotations

from typing import Any

import numpy as np

from colorlab_pro.dto.color import XY, XYZ
from colorlab_pro.dto.spectrum import Spectrum

# Cached colour-science singletons
_cmf_cache: dict[str, Any] = {}
_illuminant_sd_cache: dict[str, Any] = {}

# --- Performance caches ---
_STD_WL = np.arange(380.0, 781.0, 1.0, dtype=np.float64)
# CMF matrix cache: observer -> (wavelengths, x_bar, y_bar, z_bar)
_CMF_MATRIX: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}


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


def _is_standard_grid(wavelengths: np.ndarray) -> bool:
    """Check if wavelengths match the standard 380-780nm, 1nm grid."""
    if wavelengths.size != 401:
        return False
    return np.allclose(wavelengths, _STD_WL)


def _build_cmf_matrix(
    observer: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build cached CMF sampling matrix on the standard wavelength grid."""
    cmf = _get_cmf(observer)
    xb = np.zeros(401, dtype=np.float64)
    yb = np.zeros(401, dtype=np.float64)
    zb = np.zeros(401, dtype=np.float64)
    for i, w in enumerate(_STD_WL):
        v = cmf[w]
        xb[i] = v[0]
        yb[i] = v[1]
        zb[i] = v[2]
    return (_STD_WL.copy(), xb, yb, zb)


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
    # Fast path: standard grid + E illuminant (most common case).
    # For equal-energy (E) illuminant the spectral weight is constant at
    # all wavelengths and cancels out in the k-normalisation, so we can
    # compute XYZ with a single numpy dot product.
    if illuminant == "E" and _is_standard_grid(spectrum.wavelengths):
        if observer not in _CMF_MATRIX:
            _CMF_MATRIX[observer] = _build_cmf_matrix(observer)
        _, xb, yb, zb = _CMF_MATRIX[observer]
        delta = 1.0
        X_raw = float(np.sum(spectrum.values * xb) * delta)
        Y_raw = float(np.sum(spectrum.values * yb) * delta)
        Z_raw = float(np.sum(spectrum.values * zb) * delta)
        Y_ill = float(np.sum(yb) * delta)
        if Y_ill <= 0:
            return XYZ(X=0.0, Y=0.0, Z=0.0)
        k = 100.0 / Y_ill
        return XYZ(X=X_raw * k, Y=Y_raw * k, Z=Z_raw * k)

    # Fallback: use colour-science for non-standard grids or non-E illuminants.
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


def _dominant_wavelength_core(
    sample_xy: XY,
    white: XY,
    observer: str,
) -> tuple[float, float] | tuple[None, None]:
    """Core algorithm: find dominant wavelength and excitation purity for an xy point.

    Delegates to colour-science for accuracy and standard compliance.

    Returns:
        (wavelength_nm, excitation_purity) or (None, None) if the point is
        achromatic (excitation purity near zero).
    """
    import colour

    xy_sample = np.array([sample_xy.x, sample_xy.y])
    xy_white = np.array([white.x, white.y])
    try:
        dw_result = colour.dominant_wavelength(xy_sample, xy_white)
        dw = float(dw_result[0])
        if dw < 0:
            return None, None
        ep = float(colour.excitation_purity(xy_sample, xy_white))
        if ep < 1e-6:
            return None, None
        return dw, ep
    except Exception:
        return None, None


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
    dw, _ = _dominant_wavelength_core(c, white, observer)
    return dw


def excitation_purity(
    spectrum: Spectrum,
    *,
    white: XY | None = None,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> float | None:
    """Compute the excitation purity of a spectrum.

    Excitation purity is the ratio of the distance from the white point to
    the sample colour, divided by the distance from the white point to the
    spectrum locus along the same dominant-wavelength direction.

    Args:
        spectrum: Input spectrum.
        white: Reference white point. Defaults to the selected illuminant.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        Excitation purity as a float in [0, 1], or None if undefined.
    """
    if white is None:
        white = _get_illuminant_xy(illuminant, observer=observer)
    c = xy(spectrum, observer=observer, illuminant=illuminant)
    _, purity = _dominant_wavelength_core(c, white, observer)
    return purity
