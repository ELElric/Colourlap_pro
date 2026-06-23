"""Page widgets for analysis, mixing, gamut, optimization, and export."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from colorlab_pro.dto.color import OptimizationResult


class AnalysisResultWidget(QWidget):
    """Displays colorimetric analysis results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._xyz = QLabel("-", self)
        self._xy = QLabel("-", self)
        self._cct = QLabel("-", self)
        self._dominant = QLabel("-", self)
        self._layout.addRow("XYZ:", self._xyz)
        self._layout.addRow("xy:", self._xy)
        self._layout.addRow("CCT (K):", self._cct)
        self._layout.addRow("Dominant wavelength (nm):", self._dominant)

    def set_results(
        self,
        xyz: tuple[float, float, float],
        xy: tuple[float, float],
        cct: float,
        dominant_wavelength: float | None,
    ) -> None:
        """Populate the widget with analysis metrics."""
        self._xyz.setText(f"({xyz[0]:.3f}, {xyz[1]:.3f}, {xyz[2]:.3f})")
        self._xy.setText(f"({xy[0]:.3f}, {xy[1]:.3f})")
        self._cct.setText(f"{cct:.0f}")
        self._dominant.setText(
            f"{dominant_wavelength:.0f}" if dominant_wavelength is not None else "-"
        )


class ColorMixingResultWidget(QWidget):
    """Displays the result of a spectrum mixing operation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._mixed_xy = QLabel("-", self)
        self._mixed_xyz = QLabel("-", self)
        self._layout.addRow("Mixed xy:", self._mixed_xy)
        self._layout.addRow("Mixed XYZ:", self._mixed_xyz)

    def set_results(self, xyz: tuple[float, float, float], xy: tuple[float, float]) -> None:
        """Populate the widget with mixed color results."""
        self._mixed_xyz.setText(f"({xyz[0]:.3f}, {xyz[1]:.3f}, {xyz[2]:.3f})")
        self._mixed_xy.setText(f"({xy[0]:.3f}, {xy[1]:.3f})")


class GamutResultWidget(QWidget):
    """Displays gamut coverage and match results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._target = QLabel("-", self)
        self._coverage = QLabel("-", self)
        self._match = QLabel("-", self)
        self._layout.addRow("Target gamut:", self._target)
        self._layout.addRow("Coverage (%):", self._coverage)
        self._layout.addRow("Match (%):", self._match)

    def set_results(self, target_name: str, coverage: float, match_score: float) -> None:
        """Populate the widget with gamut comparison results."""
        self._target.setText(target_name)
        self._coverage.setText(f"{coverage:.2f}")
        self._match.setText(f"{match_score:.2f}")


class OptimizationResultWidget(QWidget):
    """Displays color-filter thickness optimization results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._summary = QLabel("No optimization run yet.", self)
        self._layout.addWidget(self._summary)

    def set_result(self, result: OptimizationResult) -> None:
        """Populate the widget with an optimization result."""
        text = (
            f"Achieved xy: ({result.achieved_xy.x:.3f}, {result.achieved_xy.y:.3f})\n"
            f"Delta xy: {result.delta_xy:.3f}\n"
            f"Converged: {result.converged}\n"
            f"Thicknesses (um): {', '.join(f'{d:.1f}' for d in result.thicknesses_um)}"
        )
        self._summary.setText(text)


class ExportOptionsWidget(QWidget):
    """Displays export format options."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._info = QLabel("Supported export formats:", self)
        self._formats = QLabel("CSV, XLSX, JSON", self)
        self._layout.addWidget(self._info)
        self._layout.addWidget(self._formats)
        self._layout.addStretch()

    def formats(self) -> list[str]:
        """Return the list of supported export formats."""
        return [fmt.strip() for fmt in self._formats.text().split(",")]
