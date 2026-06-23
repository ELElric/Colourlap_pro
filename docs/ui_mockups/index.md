# ColorLab Pro - UI Mockups

HTML specifications for 4 core UI pages. Each file contains: layout hierarchy, visual mockup, widget specs, signal/slot connections, and computation logic.

## Pages

### [01 - Spectrum Page](01_spectrum_page.md)
Import, view, and analyze spectra. Drag-and-drop CSV/XLSX import, multi-select batch operations, right-click context menu.
- Class: `SpectrumPage` | File: `spectrum_page.py` | ~858 lines

### [02 - Gamut Calculator Page](02_gamut_calculator_page.md)
Core gamut calculation. 3-column grid layout with CIE diagrams, spectrum preview, gamut results. Bottom row: chromaticity data + RGB spectrum data.
- Class: `GamutCalculatorPage` | File: `gamut_calculator_page.py` | ~1560 lines

### [03 - White Point Page](03_white_point_page.md)
White point calculation with two modes: Forward (RGB→White) and Reverse (White→RGB ratios). Dual CIE diagrams.
- Class: `WhitePointPage` | File: `white_point_page.py` | ~401 lines

### [04 - Thickness Optimizer Page](04_thickness_optimizer_page.md)
Thickness optimization. Coverage maximization and target white point modes. Background thread with progress, result table, scan curves.
- Class: `ThicknessOptimizerPage` | File: `thickness_optimizer_page.py` | ~1450 lines

## Usage Guide for AI Replication

| Step | Action |
|------|--------|
| 1 | Read the layout hierarchy tree to understand the widget tree structure |
| 2 | Look at the visual mockup for spatial layout and proportions |
| 3 | Check widget spec tables for exact property values (ranges, defaults, widths) |
| 4 | Implement signal/slot connections per the wiring table |
| 5 | Follow computation logic section for business logic |
| 6 | Apply dark theme styling (bg: `#1e1e1e`, text: `#e0e0e0`, accent: `#4fc3f7`) |

## Key Dependencies

| Component | Used In | Description |
|-----------|---------|-------------|
| CIECanvas | Gamut Calc, White Point | Custom matplotlib widget for CIE 1931 xy / CIE 1976 u'v' diagrams |
| SpectrumChartWidget | Spectrum, Gamut Calc | Custom pyqtgraph/matplotlib widget for spectrum line charts |
| _LineChartWidget | Thickness Optimizer | Subclass of SpectrumChartWidget for generic x-y line plots |
| run_in_background | Thickness Optimizer | QThreadPool-based background execution with signal callbacks |
