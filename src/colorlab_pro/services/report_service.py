"""PDF/HTML report generation service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class ReportService:
    """Generate simple HTML reports from gamut/white point/optimizer results."""

    def generate_html(
        self,
        title: str,
        sections: list[dict],
        output_path: Path,
    ) -> Path:
        """Write an HTML report with embedded tables to *output_path*."""
        html = ['<!DOCTYPE html><html><head><meta charset="utf-8"><title>', title, "</title>"]
        html.append("""<style>
body{font-family:Arial,sans-serif;margin:40px;background:#f5f5f5;color:#222}
h1{color:#1a1a1a}
.section{background:#fff;padding:20px;margin:20px 0;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
table{border-collapse:collapse;width:100%;margin-top:12px}
th,td{border:1px solid #ddd;padding:8px;text-align:left}
th{background:#333;color:#fff}
</style></head><body>""")
        html.append(f"<h1>{title}</h1>")
        html.append(f"<p>Generated at {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</p>")
        for section in sections:
            html.append(f'<div class="section"><h2>{section["title"]}</h2>')
            if section.get("text"):
                html.append(f"<p>{section['text']}</p>")
            if section.get("rows"):
                html.append("<table><thead><tr>")
                headers = section["headers"]
                html.extend([f"<th>{h}</th>" for h in headers])
                html.append("</tr></thead><tbody>")
                for row in section["rows"]:
                    html.append("<tr>")
                    for cell in row:
                        html.append(f"<td>{cell}</td>")
                    html.append("</tr>")
                html.append("</tbody></table>")
            html.append("</div>")
        html.append("</body></html>")
        output_path.write_text("".join(html), encoding="utf-8")
        return output_path

    def generate_gamut_report(
        self,
        primaries: list[dict],
        results: list[dict],
        output_path: Path,
        title: str = "Gamut Analysis Report",
    ) -> Path:
        sections = [
            {
                "title": "RGB Primaries",
                "headers": ["Channel", "x", "y"],
                "rows": [[p["ch"], p["x"], p["y"]] for p in primaries],
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
        return self.generate_html(title, sections, output_path)
