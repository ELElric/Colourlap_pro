"""ColorCalculator Engine.

Provides color math utilities:
- mix_spectra: weighted sum of spectra on a common wavelength grid
- mix_xy: weighted sum of chromaticities (for design / quick checks)
- luminance: Y from a spectrum (CIE 1931 luminance)
- color_temperature_xy: xy for a blackbody at a given CCT (Robertson's)
- color_rendering_index: CRI (Ra) approximation placeholder
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from colorlab_pro.dto.color import XY, XYZ
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.engines.spectrum_analyzer import (
    xy,
    xyz,
)

if TYPE_CHECKING:
    pass


# UI-friendly Delta E method names that colour-science accepts.
DELTA_E_METHODS = [
    "CIE 1976",
    "CIE 1994",
    "CIE 2000",
]


def _to_common_grid(
    spectra: list[Spectrum],
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Interpolate all spectra onto the first spectrum's wavelength grid.

    Returns:
        (wavelengths, list_of_values) where each values array has the
        same shape as the first spectrum's values.
    """
    from colorlab_pro.engines.spectrum_normalizer import interpolate

    if not spectra:
        raise ValueError("spectra list must not be empty")
    ref_wl = spectra[0].wavelengths
    aligned = [spectra[0].values.copy()]
    for s in spectra[1:]:
        if s.wavelengths.shape == ref_wl.shape and np.allclose(s.wavelengths, ref_wl):
            aligned.append(s.values.copy())
        else:
            interp = interpolate(s, method="cubic")
            # interpolate() produces a grid starting at s.wavelengths[0]
            # with step 1 nm. We then resample to ref_wl.
            new_v = np.interp(ref_wl, interp.wavelengths, interp.values)
            aligned.append(new_v)
    return ref_wl, aligned


def mix_spectra(
    spectra: list[Spectrum],
    weights: list[float] | None = None,
) -> Spectrum:
    """Compute the weighted sum of spectra on a common wavelength grid.

    Used for additive color mixing of primary spectra (e.g. R + G + B LEDs).

    Args:
        spectra: List of spectra to mix.
        weights: Per-spectrum weights. Defaults to all 1.0.

    Returns:
        New Spectrum with values = sum(weight_i * values_i).
    """
    if not spectra:
        raise ValueError("spectra must not be empty")
    n = len(spectra)
    if weights is None:
        weights = [1.0] * n
    if len(weights) != n:
        raise ValueError(f"weights length ({len(weights)}) must match spectra length ({n})")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    if sum(weights) == 0:
        raise ValueError("weights sum must be > 0")

    wl, aligned = _to_common_grid(spectra)
    mixed = np.zeros_like(aligned[0])
    for v, w in zip(aligned, weights, strict=True):
        mixed = mixed + w * v

    return Spectrum(
        wavelengths=wl,
        values=mixed,
        unit=spectra[0].unit,
        meta={"mixed_from": n, "weights": list(weights)},
    )


def mix_xy(
    xy_list: list[XY],
    weights: list[float] | None = None,
) -> XY:
    """Compute additive-mixed white point from RGB chromaticities.

    Physically correct: converts each xy to XYZ (assuming Y=1),
    sums weighted XYZ, then converts back to xy via colour-science.

    Args:
        xy_list: List of XY chromaticities (R, G, B).
        weights: Per-channel weights (relative luminance). Defaults to all 1.0.

    Returns:
        Mixed white point XY.
    """
    import colour

    if not xy_list:
        raise ValueError("xy_list must not be empty")
    n = len(xy_list)
    if weights is None:
        weights = [1.0] * n
    if len(weights) != n:
        raise ValueError(f"weights length ({len(weights)}) must match xy_list length ({n})")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    if sum(weights) == 0:
        raise ValueError("weights sum must be > 0")

    # Convert each xy to XYZ (Y=1.0), then sum weighted
    total_xyz = np.zeros(3, dtype=np.float64)
    for p, w in zip(xy_list, weights, strict=True):
        xyz_arr = colour.xy_to_XYZ(np.array([p.x, p.y]))
        total_xyz += w * xyz_arr

    # Convert summed XYZ back to xy
    mixed_xy = colour.XYZ_to_xy(total_xyz)
    return XY(x=float(mixed_xy[0]), y=float(mixed_xy[1]))


def mix_xyz(
    spectra: list[Spectrum],
    weights: list[float] | None = None,
) -> XYZ:
    """Compute additive XYZ mixing (the physically correct way).

    Args:
        spectra: List of spectra to mix.
        weights: Per-spectrum weights. Defaults to all 1.0.

    Returns:
        Total XYZ of the mixture.
    """
    if not spectra:
        raise ValueError("spectra must not be empty")
    n = len(spectra)
    if weights is None:
        weights = [1.0] * n
    if len(weights) != n:
        raise ValueError(f"weights length ({len(weights)}) must match spectra length ({n})")

    total = np.zeros(3, dtype=np.float64)
    total_w = 0.0
    for s, w in zip(spectra, weights, strict=True):
        c = xyz(s)
        total = total + w * np.array([c.X, c.Y, c.Z], dtype=np.float64)
        total_w += w
    if total_w == 0:
        raise ValueError("weights sum must be > 0")
    return XYZ(X=float(total[0]), Y=float(total[1]), Z=float(total[2]))


def luminance(
    spectrum: Spectrum,
    *,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> float:
    """Compute the CIE luminance (Y) of a spectrum.

    Args:
        spectrum: Input spectrum.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        Y (luminance) in the same arbitrary unit as the input values.
    """
    return xyz(spectrum, observer=observer, illuminant=illuminant).Y


def delta_uv(
    spectrum: Spectrum,
    reference: XY | None = None,
    *,
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> tuple[float, float]:
    """Compute the (CCT, Duv) of a spectrum relative to the Planckian locus.

    Duv is the signed perpendicular distance from the sample's chromaticity
    to the Planckian locus in CIE 1960 UCS (u, v) space. A positive Duv
    means the sample is "greenish" (above the locus), negative means
    "pinkish" (below the locus).

    Uses colour-science's Ohno 2013 method for accurate Duv computation.

    Args:
        spectrum: Input spectrum.
        reference: Unused (kept for API compatibility). Duv is always
            measured relative to the Planckian locus, not a fixed point.
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        (CCT, Duv) tuple. CCT in Kelvin, Duv as signed distance.
    """
    import colour

    from colorlab_pro.engines.spectrum_analyzer import cct_mccamy

    c = xy(spectrum, observer=observer, illuminant=illuminant)

    # Convert xy to CIE 1960 UCS (u, v) for Planckian locus comparison.
    # u = 4x / (-2x + 12y + 3), v = 6y / (-2x + 12y + 3)
    denom = -2.0 * c.x + 12.0 * c.y + 3.0
    if denom == 0:
        return 0.0, 0.0
    u = 4.0 * c.x / denom
    v = 6.0 * c.y / denom

    cct = cct_mccamy(spectrum, observer=observer, illuminant=illuminant)

    # Compute Duv using Ohno 2013 via colour-science.
    # uv_to_CCT_Ohno2013 returns (CCT, Duv) from (u, v) in 1960 UCS.
    try:
        uv = np.array([u, v])
        _, duv = colour.temperature.uv_to_CCT_Ohno2013(uv)
        duv = float(duv)
    except Exception:  # noqa: BLE001
        # Fallback: if Ohno 2013 fails (e.g. too far from locus),
        # approximate Duv as distance to D65 in 1960 UCS.
        ref_denom = -2.0 * 0.3127 + 12.0 * 0.3290 + 3.0
        ref_u = 4.0 * 0.3127 / ref_denom
        ref_v = 6.0 * 0.3290 / ref_denom
        duv_vec = np.array([u - ref_u, v - ref_v], dtype=np.float64)
        mag = float(np.linalg.norm(duv_vec))
        duv = mag if v > ref_v else -mag

    return cct, duv


def delta_e(
    spectrum_a: Spectrum,
    spectrum_b: Spectrum,
    *,
    method: str = "CIE 2000",
    observer: str = "CIE 1931 2 Degree Standard Observer",
    illuminant: str = "E",
) -> float:
    """Compute the colour difference (Delta E) between two spectra.

    Args:
        spectrum_a: First spectrum.
        spectrum_b: Second spectrum.
        method: Delta E method (CIE 1976, CIE 1994, CIE 2000).
        observer: Standard observer name.
        illuminant: Illuminant name.

    Returns:
        Delta E value.
    """
    import colour

    xyz_a = xyz(spectrum_a, observer=observer, illuminant=illuminant)
    xyz_b = xyz(spectrum_b, observer=observer, illuminant=illuminant)
    ref_xy = (
        colour.CCS_ILLUMINANTS[observer][illuminant]
        if observer in colour.CCS_ILLUMINANTS
        else colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"][illuminant]
    )
    lab_a = colour.XYZ_to_Lab(
        np.array([xyz_a.X, xyz_a.Y, xyz_a.Z], dtype=np.float64), illuminant=ref_xy
    )
    lab_b = colour.XYZ_to_Lab(
        np.array([xyz_b.X, xyz_b.Y, xyz_b.Z], dtype=np.float64), illuminant=ref_xy
    )
    return float(colour.delta_E(lab_a, lab_b, method=method))
