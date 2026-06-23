"""Unit tests for colorlab_pro.engines.gamut_calculator (T-05)."""

from __future__ import annotations

import pytest

from colorlab_pro.dto.color import XY, Gamut
from colorlab_pro.engines import gamut_calculator as gc

# ---- fixtures ----


@pytest.fixture
def srgb() -> Gamut:
    return gc.standard_gamuts("sRGB")


@pytest.fixture
def dci_p3() -> Gamut:
    return gc.standard_gamuts("DCI-P3")


@pytest.fixture
def adobe_rgb() -> Gamut:
    return gc.standard_gamuts("Adobe RGB")


@pytest.fixture
def ntsc() -> Gamut:
    return gc.standard_gamuts("NTSC")


@pytest.fixture
def identical_device(srgb: Gamut) -> Gamut:
    return Gamut(
        name="identical",
        red=srgb.red,
        green=srgb.green,
        blue=srgb.blue,
        white=srgb.white,
    )


# ---- standard_gamuts / build_gamut ----


class TestStandardGamuts:
    def test_srgb(self) -> None:
        g = gc.standard_gamuts("sRGB")
        assert g.red == pytest.approx((0.6400, 0.3300))
        assert g.green == pytest.approx((0.3000, 0.6000))
        assert g.blue == pytest.approx((0.1500, 0.0600))
        assert g.white == pytest.approx((0.3127, 0.3290))

    def test_dci_p3(self) -> None:
        g = gc.standard_gamuts("DCI-P3")
        assert g.red == pytest.approx((0.6800, 0.3200))
        assert g.green == pytest.approx((0.2650, 0.6900))
        assert g.blue == pytest.approx((0.1500, 0.0600))

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown standard gamut"):
            gc.standard_gamuts("Rec2020")

    def test_build_gamut_from_primaries(self) -> None:
        g = gc.build_gamut_from_primaries(
            name="custom",
            red=XY(0.7, 0.3),
            green=XY(0.2, 0.7),
            blue=XY(0.1, 0.05),
            white=XY(0.33, 0.33),
        )
        assert g.name == "custom"
        assert g.red == (0.7, 0.3)
        assert g.green == (0.2, 0.7)
        assert g.blue == (0.1, 0.05)
        assert g.white == (0.33, 0.33)


# ---- area ----


class TestArea:
    def test_srgb_area_positive(self, srgb: Gamut) -> None:
        a = gc.area(srgb)
        assert a > 0.05

    def test_area_units(self) -> None:
        # Larger triangle should have larger area
        big = Gamut(
            name="big",
            red=(1.0, 0.0),
            green=(0.0, 1.0),
            blue=(0.0, 0.0),
            white=(1 / 3, 1 / 3),
        )
        small = Gamut(
            name="small",
            red=(0.5, 0.25),
            green=(0.25, 0.5),
            blue=(0.1, 0.1),
            white=(0.3, 0.3),
        )
        assert gc.area(big) > gc.area(small)


# ---- coverage ----


class TestCoverage:
    def test_self_coverage_100(self, srgb: Gamut, identical_device: Gamut) -> None:
        assert gc.coverage(srgb, identical_device) == pytest.approx(100.0)

    def test_srgb_vs_dci_p3(self, srgb: Gamut, dci_p3: Gamut) -> None:
        cov = gc.coverage(dci_p3, srgb)
        # sRGB does not fully cover DCI-P3; expected ~73%
        assert 50.0 <= cov <= 110.0
        assert cov < 100.0

    def test_srgb_covers_adobe_smaller(self, srgb: Gamut, adobe_rgb: Gamut) -> None:
        # coverage = device_area / target_area; Adobe RGB is larger than sRGB
        cov = gc.coverage(srgb, adobe_rgb)
        assert cov > 100.0  # Adobe RGB area > sRGB area

    def test_zero_area_target_raises(self) -> None:
        degenerate = Gamut(
            name="zero",
            red=(0.3, 0.3),
            green=(0.3, 0.3),
            blue=(0.3, 0.3),
            white=(0.3, 0.3),
        )
        device = Gamut(
            name="device",
            red=(0.6, 0.3),
            green=(0.3, 0.6),
            blue=(0.1, 0.1),
            white=(0.3127, 0.3290),
        )
        with pytest.raises(ValueError, match="zero area"):
            gc.coverage(degenerate, device)


# ---- match ----


class TestMatch:
    def test_self_match_100(self, srgb: Gamut, identical_device: Gamut) -> None:
        assert gc.match(srgb, identical_device) == pytest.approx(100.0)

    def test_perfect_zero_delta(self, srgb: Gamut) -> None:
        assert gc.match(srgb, srgb) == pytest.approx(100.0)

    def test_smaller_device_lower_match(self, srgb: Gamut) -> None:
        # device is a subset of sRGB → intersection < sRGB area → match < 100%
        smaller = Gamut(
            name="smaller",
            red=(0.55, 0.35),
            green=(0.35, 0.55),
            blue=(0.20, 0.15),
            white=srgb.white,
        )
        m = gc.match(srgb, smaller)
        assert 0.0 < m < 100.0

    def test_no_overlap_is_zero(self) -> None:
        # two non-overlapping triangles
        target = Gamut(
            name="target",
            red=(0.8, 0.1),
            green=(0.7, 0.2),
            blue=(0.6, 0.1),
            white=(0.3127, 0.3290),
        )
        device = Gamut(
            name="device",
            red=(0.1, 0.8),
            green=(0.2, 0.7),
            blue=(0.1, 0.6),
            white=(0.3127, 0.3290),
        )
        m = gc.match(target, device)
        assert m == pytest.approx(0.0)


class TestCIE1976:
    def test_xy_to_uv(self) -> None:
        u, v = gc.xy_to_uv(0.3127, 0.3290)
        # Approximate known u'v' for D65
        assert u == pytest.approx(0.1978, abs=0.001)
        assert v == pytest.approx(0.4683, abs=0.001)

    def test_coverage_range(self, srgb: Gamut, dci_p3: Gamut) -> None:
        cov_1931 = gc.coverage(dci_p3, srgb)
        # Coverage = device_area / target_area; can exceed 100%
        assert cov_1931 > 0.0

    def test_coverage_1976_range(self, srgb: Gamut, dci_p3: Gamut) -> None:
        cov = gc.coverage_1976(dci_p3, srgb)
        assert cov > 0.0

    def test_match_1976_range(self, srgb: Gamut, dci_p3: Gamut) -> None:
        m = gc.match_1976(dci_p3, srgb)
        assert 0.0 <= m <= 100.0


# ---- match_spectrum ----


class TestMatchSpectrum:
    def test_same_point_100(self) -> None:
        p = XY(0.3, 0.4)
        assert gc.match_spectrum(p, p) == pytest.approx(100.0)

    def test_half_saturation(self) -> None:
        target = XY(0.3, 0.3)
        sample = XY(0.35, 0.3)
        assert gc.match_spectrum(target, sample) == pytest.approx(50.0, abs=1e-6)

    def test_at_saturation_zero(self) -> None:
        target = XY(0.3, 0.3)
        sample = XY(0.4, 0.3)
        assert gc.match_spectrum(target, sample) == pytest.approx(0.0)

    def test_beyond_saturation_zero(self) -> None:
        target = XY(0.3, 0.3)
        sample = XY(0.5, 0.3)
        assert gc.match_spectrum(target, sample) == pytest.approx(0.0)

    def test_custom_saturation(self) -> None:
        target = XY(0.0, 0.0)
        sample = XY(0.1, 0.0)
        assert gc.match_spectrum(target, sample, saturation=0.2) == pytest.approx(50.0)


# ---- contains ----


class TestContains:
    def test_d65_inside_srgb(self, srgb: Gamut) -> None:
        assert gc.contains(srgb, XY(0.3127, 0.3290)) is True

    def test_red_primary_interior(self, srgb: Gamut) -> None:
        # shapely.contains excludes boundary; test an interior point
        assert gc.contains(srgb, XY(0.5, 0.35)) is True

    def test_outside_gamut(self, srgb: Gamut) -> None:
        assert gc.contains(srgb, XY(0.1, 0.8)) is False
