"""Controllers layer — mediates between UI and Services."""

from __future__ import annotations

from colorlab_pro.controllers.color_controller import ColorController, GamutResult, MixResult
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import (
    OptimizationController,
    ThicknessResult,
    WhitePointResult,
)
from colorlab_pro.controllers.project_controller import ProjectController, ProjectInfo
from colorlab_pro.controllers.spectrum_controller import SpectrumController, SpectrumSummary

__all__ = [
    "MainController",
    "ProjectController",
    "ProjectInfo",
    "SpectrumController",
    "SpectrumSummary",
    "ColorController",
    "MixResult",
    "GamutResult",
    "OptimizationController",
    "WhitePointResult",
    "ThicknessResult",
]
