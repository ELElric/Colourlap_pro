"""Tests for WebViewPage backend slots."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.pages.gamut_calculator_page import GamutPageBackend
from colorlab_pro.ui.pages.thickness_optimizer_page import OptimizerPageBackend
from colorlab_pro.ui.pages.white_point_page import WhitePointPageBackend


@pytest.fixture
def controllers(tmp_path: Path, qtbot):
    """Provide initialized controllers with a project."""
    main = MainController()
    main.initialize(db_path=tmp_path / "test.db")
    qtbot.addWidget(main.create_window())

    proj_ctrl = ProjectController(main)
    pid = proj_ctrl.create_project("Test Project")
    main.set_current_project(pid)

    spec_ctrl = SpectrumController(main)
    color_ctrl = ColorController(main)
    opt_ctrl = OptimizationController(main)
    yield {"main": main, "spec": spec_ctrl, "color": color_ctrl, "opt": opt_ctrl}
    main.shutdown()


@pytest.fixture
def rgb_spectra(controllers):
    """Import three LED-like spectra and return their ids."""
    spec_ctrl = controllers["spec"]
    ids = []
    for name, peak in [("Red", 630.0), ("Green", 525.0), ("Blue", 450.0)]:
        wavelengths = np.linspace(380, 780, 401)
        values = np.exp(-((wavelengths - peak) ** 2) / (2 * 20**2))
        sid = spec_ctrl.import_spectrum(Spectrum(wavelengths=wavelengths, values=values), name=name)
        ids.append(sid)
    return ids


class TestGamutCalculatorBackend:
    def test_get_initial_data(self, controllers, qtbot) -> None:
        backend = GamutPageBackend(controllers["spec"], controllers["color"])
        raw = backend.get_initial_data()
        data = json.loads(raw)
        assert "spectra" in data
        assert "results" in data
        assert data.get("error") is None

    def test_calculate_gamut(self, controllers, rgb_spectra, qtbot) -> None:
        backend = GamutPageBackend(controllers["spec"], controllers["color"])
        rid, gid, bid = rgb_spectra
        raw = backend.calculate_gamut(str(rid), str(gid), str(bid))
        data = json.loads(raw)
        assert data.get("error") is None
        assert "primaries" in data
        assert "results" in data
        assert len(data["results"]) == 4
        standards = [r["standard"] for r in data["results"]]
        assert "sRGB" in standards and "BT2020" in standards
        for r in data["results"]:
            assert isinstance(r["coverage_1931"], (int, float))
            assert isinstance(r["match_1931"], (int, float))

    def test_calculate_gamut_invalid_id(self, controllers, qtbot) -> None:
        backend = GamutPageBackend(controllers["spec"], controllers["color"])
        raw = backend.calculate_gamut("9999", "9999", "9999")
        data = json.loads(raw)
        assert "error" in data


class TestWhitePointBackend:
    def test_get_initial_data(self, controllers, qtbot) -> None:
        backend = WhitePointPageBackend(controllers["color"])
        raw = backend.get_initial_data()
        data = json.loads(raw)
        assert data["white_xy"] == [0.3127, 0.329]
        assert "results" in data

    def test_calculate_white_point_equal_energy(self, controllers, qtbot) -> None:
        backend = WhitePointPageBackend(controllers["color"])
        payload = json.dumps(
            {
                "red_xy": [0.64, 0.33],
                "green_xy": [0.3, 0.6],
                "blue_xy": [0.15, 0.06],
                "ratios": {"R": 1.0, "G": 1.0, "B": 1.0},
            }
        )
        raw = backend.calculate_white_point(payload)
        data = json.loads(raw)
        assert data.get("error") is None
        assert "white_xy" in data
        assert "white_uv" in data
        assert "cct" in data
        assert len(data["results"]) == 4
        wx, wy = data["white_xy"]
        assert 0.0 <= wx <= 1.0 and 0.0 <= wy <= 1.0

    def test_calculate_white_point_zero_ratios(self, controllers, qtbot) -> None:
        backend = WhitePointPageBackend(controllers["color"])
        payload = json.dumps(
            {
                "red_xy": [0.64, 0.33],
                "green_xy": [0.3, 0.6],
                "blue_xy": [0.15, 0.06],
                "ratios": {"R": 0.0, "G": 0.0, "B": 0.0},
            }
        )
        raw = backend.calculate_white_point(payload)
        data = json.loads(raw)
        assert data.get("error") is None
        assert data["white_xy"] == [0.0, 0.0]


class TestOptimizerBackend:
    def test_get_initial_data(self, controllers, qtbot) -> None:
        backend = OptimizerPageBackend(controllers["spec"], controllers["color"], controllers["opt"])
        raw = backend.get_initial_data()
        data = json.loads(raw)
        assert "spectra" in data
        assert "results" in data
        assert "best" in data

    def test_optimize_with_same_source_and_cf(self, controllers, rgb_spectra, qtbot) -> None:
        backend = OptimizerPageBackend(controllers["spec"], controllers["color"], controllers["opt"])
        rid, gid, bid = rgb_spectra
        payload = json.dumps(
            {
                "source_ids": [rid, gid, bid],
                "cf_ids": [rid, gid, bid],
                "bounds": [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]],
                "target_standard": "BT2020",
            }
        )
        raw = backend.optimize(payload)
        data = json.loads(raw)
        assert data.get("error") is None
        assert "results" in data
        assert data["best"]["thickness_r"] == 1.0
        assert data["best"]["thickness_g"] == 1.0
        assert data["best"]["thickness_b"] == 1.0

    def test_optimize_invalid_spectrum_count(self, controllers, qtbot) -> None:
        backend = OptimizerPageBackend(controllers["spec"], controllers["color"], controllers["opt"])
        payload = json.dumps(
            {
                "source_ids": [1],
                "cf_ids": [1, 2, 3],
                "bounds": [[0, 1], [0, 1], [0, 1]],
                "target_standard": "BT2020",
            }
        )
        raw = backend.optimize(payload)
        data = json.loads(raw)
        assert "error" in data
