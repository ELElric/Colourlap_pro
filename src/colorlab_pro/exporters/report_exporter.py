"""Report exporter facade.

Wraps ReportService so that UI pages can generate PDF/HTML reports
through a stable exporter interface.
"""

from __future__ import annotations

from pathlib import Path

from colorlab_pro.services.report_service import ReportService


class ReportExporter:
    """Generate HTML/PDF reports from gamut and white-point results."""

    def __init__(self) -> None:
        self._service = ReportService()

    def export_gamut_report(
        self,
        primaries: list[dict],
        results: list[dict],
        output_path: Path,
        title: str = "Gamut Analysis Report",
    ) -> Path:
        """Export a gamut analysis report to *output_path*."""
        return self._service.generate_gamut_report(
            primaries, results, output_path, title=title
        )

    def export_white_point_report(
        self,
        white_xy: tuple[float, float],
        white_uv: tuple[float, float],
        cct: float,
        ratios: dict[str, float],
        results: list[dict],
        output_path: Path,
        title: str = "White Point Analysis Report",
    ) -> Path:
        """Export a white point analysis report to *output_path*."""
        sections = [
            {
                "title": "White Point",
                "headers": ["Metric", "Value"],
                "rows": [
                    ["xy", f"{white_xy[0]:.4f}, {white_xy[1]:.4f}"],
                    ["u'v'", f"{white_uv[0]:.4f}, {white_uv[1]:.4f}"],
                    ["CCT", f"{cct:.0f} K"],
                    ["Ratios R:G:B", f"{ratios['R']:.3f} : {ratios['G']:.3f} : {ratios['B']:.3f}"],
                ],
            },
            {
                "title": "Gamut Performance",
                "headers": ["Standard", "Coverage 1931 (%)", "Match 1931 (%)", "Coverage 1976 (%)", "Match 1976 (%)"],
                "rows": [
                    [r["standard"], r["coverage_1931"], r["match_1931"], r["coverage_1976"], r["match_1976"]]
                    for r in results
                ],
            },
        ]
        return self._service.generate_html(title, sections, output_path)


def export_gamut_report(
    primaries: list[dict],
    results: list[dict],
    output_path: Path,
    title: str = "Gamut Analysis Report",
) -> Path:
    """Convenience function for exporting a gamut report."""
    return ReportExporter().export_gamut_report(
        primaries, results, output_path, title=title
    )
