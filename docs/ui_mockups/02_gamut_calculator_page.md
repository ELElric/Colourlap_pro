# 02 - Gamut Calculator Page

`gamut_calculator_page.py` | Class: `GamutCalculatorPage(QWidget)` | ~1560 lines

Core gamut calculation page. 3-column grid layout with CIE diagrams, spectrum preview, gamut results. Bottom row: chromaticity data + RGB spectrum data.

---

## 1. Layout Hierarchy (Widget Tree)

```
QVBoxLayout outer_layout
├── QWidget mode_widget
│   └── QHBoxLayout
│       ├── QLabel("Mode:")
│       ├── QComboBox _mode_combo                    items=["RGB + Color Filter", "White + Color Filter"]
│       ├── QCheckBox _show_original_cb              text="Show Original", checked
│       ├── QCheckBox _show_filtered_cb              text="Show Filtered", checked
│       ├── QCheckBox _show_white_cb                 text="Show White Point", checked
│       ├── QCheckBox _show_trajectory_cb            text="Show Trajectory", checked
│       ├── QCheckBox _show_triangle_cb              text="Show Triangle", checked
│       ├── QCheckBox _ref_gamut_cbs["sRGB"]         text="sRGB", unchecked
│       ├── QCheckBox _ref_gamut_cbs["NTSC"]         text="NTSC", checked
│       ├── QCheckBox _ref_gamut_cbs["DCI-P3"]       text="DCI-P3", checked
│       ├── QCheckBox _ref_gamut_cbs["BT2020"]       text="BT2020", checked
│       └── stretch
│
├── QGroupBox("Input Parameters")
│   └── QSplitter(H) sizes=[180, 180, 260]
│       ├── QWidget [Spectrum Panel]
│       │   └── QVBoxLayout
│       │       ├── QLabel("<b>Spectrum</b>")
│       │       ├── QWidget _rgb_group_widget
│       │       │   ├── _SpectrumSelector("R") -> _rgb_sel_R
│       │       │   ├── _SpectrumSelector("G") -> _rgb_sel_G
│       │       │   └── _SpectrumSelector("B") -> _rgb_sel_B
│       │       └── QWidget _white_group_widget [hidden]
│       │           └── _SpectrumSelector("W") -> _white_sel
│       ├── QWidget [Filter Panel]
│       │   └── QVBoxLayout
│       │       ├── QLabel("<b>Color Filter</b>")
│       │       ├── _SpectrumSelector("RCF") -> _filter_sel_RCF
│       │       ├── _SpectrumSelector("GCF") -> _filter_sel_GCF
│       │       └── _SpectrumSelector("BCF") -> _filter_sel_BCF
│       └── QWidget [Thickness Panel]
│           └── QVBoxLayout
│               ├── QLabel("<b>Thickness (μm)</b>")
│               ├── _ThicknessControl("RCF") -> _thickness_RCF
│               ├── _ThicknessControl("GCF") -> _thickness_GCF
│               └── _ThicknessControl("BCF") -> _thickness_BCF
│
├── QWidget row1_widget [stretch=12]
│   └── QGridLayout setColumnStretch(0,1), (1,1), (2,1)  <-- THREE EQUAL COLUMNS
│       ├── [0,0] QGroupBox("CIE Chromaticity Diagrams")
│       │   └── QTabWidget _cie_tab_widget
│       │       ├── Tab "CIE 1931 xy"
│       │       │   └── CIECanvas(mode="xy") _cie_xy_canvas
│       │       └── Tab "CIE 1976 u'v'"
│       │           └── CIECanvas(mode="uv") _cie_uv_canvas
│       ├── [0,1] QGroupBox("Spectrum Preview")
│       │   └── QTabWidget _spectrum_tab_widget
│       │       ├── Tab "Filtered Spectrum"
│       │       │   └── SpectrumChartWidget _filtered_chart
│       │       ├── Tab "Original Spectrum"
│       │       │   └── SpectrumChartWidget _original_chart
│       │       └── Tab "Compare Mode"
│       │           └── QWidget
│       │               ├── QHBoxLayout [6 QCheckBoxes for curves]
│       │               │   ├── QCheckBox("RCF")     color=#FF8888
│       │               │   ├── QCheckBox("GCF")     color=#88FF88
│       │               │   ├── QCheckBox("BCF")     color=#88AAFF
│       │               │   ├── QCheckBox("LED R")   color=#FF4444
│       │               │   ├── QCheckBox("LED G")   color=#44FF44
│       │               │   └── QCheckBox("LED B")   color=#4488FF
│       │               └── SpectrumChartWidget _compare_chart  minHeight=160
│       └── [0,2] QGroupBox("Gamut Result")
│           └── QVBoxLayout
│               ├── QLabel("<b>CIE 1931 xy</b>")
│               ├── QTableWidget(4, 3) _gamut_table_1931
│               │   Headers: ["Standard", "Coverage (%)", "Match (%)"]
│               │   Rows: sRGB, NTSC, DCI-P3, BT2020
│               ├── QLabel("<b>CIE 1976 u'v'</b>")
│               └── QTableWidget(4, 3) _gamut_table_1976
│                   Headers: ["Standard", "Coverage (%)", "Match (%)"]
│                   Rows: sRGB, NTSC, DCI-P3, BT2020
│
└── QGroupBox("Data") [stretch=5]
    └── QGridLayout setColumnStretch(0,1), (1,1)  <-- TWO EQUAL COLUMNS
        ├── [0,0] QLabel("<b>RGBW Chromaticity Data</b>")
        ├── [0,1] QLabel("<b>RGB Spectrum Data</b>")
        ├── [1,0] QTableWidget(4, 8) _chromaticity_table
        │   Headers: ["Channel", "x", "y", "u'", "v'", "X", "Y", "CCT"]
        │   Rows: R, G, B, White
        └── [1,1] QTableWidget(3, 5) _spectrum_data_table
            Headers: ["Channel", "Peak (nm)", "FWHM (nm)", "Dom. λ (nm)", "Purity"]
            Rows: R, G, B
```

---

## 2. Visual Mockup

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Mode: [RGB + Color Filter ▾]  ☑Show Original ☑Show Filtered ☑Show White Point │
│       ☑Show Trajectory ☑Show Triangle  ☐sRGB ☑NTSC ☑DCI-P3 ☑BT2020            │
├──────────────────────────────────────────────────────────────────────────────────┤
│  ┌─ Input Parameters ──────────────────────────────────────────────────────────┐ │
│  │  Spectrum         │  Color Filter       │  Thickness (μm)                  │ │
│  │  ─────────        │  ───────────        │  ─────────────                   │ │
│  │  R [▾] [Paste]   │  RCF [▾] [Paste]   │  RCF [-][1.00][+] Step:[0.01]   │ │
│  │  G [▾] [Paste]   │  GCF [▾] [Paste]   │  GCF [-][1.00][+] Step:[0.01]   │ │
│  │  B [▾] [Paste]   │  BCF [▾] [Paste]   │  BCF [-][1.00][+] Step:[0.01]   │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────┬─────────────────────────┬─────────────────────────────┤
│  CIE Chromaticity       │  Spectrum Preview       │  Gamut Result               │
│  [CIE 1931 xy][1976u'v']│  [Filtered][Original]  │  ┌─ CIE 1931 xy ──────────┐ │
│                         │  [Compare Mode]         │  │Standard│Cov(%)│Match(%)│ │
│  ┌───────────────────┐  │                         │  │sRGB    │ --   │ --     │ │
│  │                   │  │  ┌───────────────────┐  │  │NTSC    │ --   │ --     │ │
│  │   CIE Diagram     │  │  │                   │  │  │DCI-P3  │ --   │ --     │ │
│  │   (xy / u'v')     │  │  │  Spectrum Chart   │  │  │BT2020  │ --   │ --     │ │
│  │                   │  │  │                   │  │  └────────────────────────┘ │
│  │                   │  │  └───────────────────┘  │  ┌─ CIE 1976 u'v' ─────────┐ │
│  └───────────────────┘  │                         │  │Standard│Cov(%)│Match(%)│ │
│                         │                         │  │sRGB    │ --   │ --     │ │
│                         │                         │  │NTSC    │ --   │ --     │ │
│                         │                         │  │DCI-P3  │ --   │ --     │ │
│                         │                         │  │BT2020  │ --   │ --     │ │
│                         │                         │  └────────────────────────┘ │
├─────────────────────────┴─────────────────────────┴─────────────────────────────┤
│  ┌─ Data ──────────────────────────────┬─ Data ───────────────────────────────┐ │
│  │  RGBW Chromaticity Data             │  RGB Spectrum Data                   │ │
│  │  Ch │ x    │ y    │ u'   │ v'  ... │  Ch │ Peak │ FWHM │ Dom.λ │ Purity  │ │
│  │  R  │ --   │ --   │ --   │ --  ... │  R  │ --   │ --   │ --    │ --      │ │
│  │  G  │ --   │ --   │ --   │ --  ... │  G  │ --   │ --   │ --    │ --      │ │
│  │  B  │ --   │ --   │ --   │ --  ... │  B  │ --   │ --   │ --    │ --      │ │
│  │  W  │ --   │ --   │ --   │ --  ... │  └─────┴──────┴──────┴───────┴────────┘ │
│  └─────────────────────────────────────┴──────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Helper Component: _SpectrumSelector

`_SpectrumSelector(QWidget)` — Reusable spectrum selector widget.

| Property | Value |
|----------|-------|
| layout | QHBoxLayout, margins=0, spacing=6 |
| QLabel | text=channel (e.g. "R"), fixedWidth=24, colored per channel |
| QComboBox | minWidth=60, SizeAdjustPolicy=AdjustToMinimumContentsLengthWithIcon |
| QPushButton("Paste") | fixedWidth=textWidth+20, tooltip="Paste spectrum from clipboard" |
| minimumWidth | 160 |
| Signal | `selectionChanged()` (no args, forwarded from QComboBox.currentIndexChanged) |

### Channel Colors

| Channel | Color |
|---------|-------|
| R | `#FF4444` |
| G | `#44FF44` |
| B | `#4488FF` |
| RCF | `#FF8888` |
| GCF | `#88FF88` |
| BCF | `#88AAFF` |

---

## 4. Helper Component: _ThicknessControl

`_ThicknessControl(QWidget)` — Thickness control with [-][value][+] and step setting.

| Property | Value |
|----------|-------|
| layout | QHBoxLayout, margins=0, spacing=4 |
| QPushButton("-") | minWidth=40 |
| QDoubleSpinBox | range=0.0~5.0, step=0.01, decimals=2, default=1.0, minWidth=80 |
| QPushButton("+") | minWidth=40 |
| QLabel("Step:") | - |
| QDoubleSpinBox (step) | range=0.01~1.0, step=0.01, decimals=2, default=0.01, minWidth=70 |
| minimumWidth | 260 |
| Signal | `valueChanged(float)` |

---

## 5. Table Specifications

### Gamut Tables (_gamut_table_1931, _gamut_table_1976)

| Property | Value |
|----------|-------|
| columnCount | 3 |
| horizontalHeaderLabels | `["Standard", "Coverage (%)", "Match (%)"]` |
| rowCount | 4 (sRGB, NTSC, DCI-P3, BT2020) |
| horizontalScrollMode | ScrollPerPixel |
| verticalHeaderVisible | False |
| editTriggers | NoEditTriggers |
| selectionMode | NoSelection |
| All columns | Stretch (equal width) |

### Chromaticity Table (_chromaticity_table)

| Property | Value |
|----------|-------|
| columnCount | 8 |
| horizontalHeaderLabels | `["Channel", "x", "y", "u'", "v'", "X", "Y", "CCT"]` |
| rowCount | 4 (R, G, B, White) |
| All columns | Stretch (equal width) |

### Spectrum Data Table (_spectrum_data_table)

| Property | Value |
|----------|-------|
| columnCount | 5 |
| horizontalHeaderLabels | `["Channel", "Peak (nm)", "FWHM (nm)", "Dom. λ (nm)", "Purity"]` |
| rowCount | 3 (R, G, B) |
| All columns | Stretch (equal width) |

---

## 6. Signal/Slot Connections

| Signal | Slot | Description |
|--------|------|-------------|
| `_mode_combo.currentIndexChanged` | `_on_mode_changed` | Switch RGB/White mode, toggle widget visibility |
| `_rgb_sel_R/G/B.selectionChanged` | `_on_rgb_selection_changed(ch)` | Load spectrum, trigger recalculation |
| `_white_sel.selectionChanged` | `_on_white_selection_changed` | Load white spectrum |
| `_filter_sel_RCF/GCF/BCF.selectionChanged` | `_on_filter_selection_changed(ch)` | Load filter spectrum, auto-fill thickness |
| `_thickness_RCF/GCF/BCF.valueChanged` | `_on_thickness_changed(ch, val)` | Real-time recalculation |
| `_show_*_cb.stateChanged` | `_on_show_options_changed` | Sync both CIE canvases |
| `_ref_gamut_cbs.*.stateChanged` | `_on_reference_gamuts_changed` | Update reference gamuts on CIE canvases |
| `*.Paste clicked` | `_on_paste()` | Parse clipboard, import spectrum |
| `page_about_to_show(idx)` | `_on_page_show` | Refresh spectrum list, auto-select defaults |

---

## 7. Core Calculation Flow

`_recalculate()` Pipeline:

1. Build active_spectra (RGB or White*3)
2. Apply Beer-Lambert filter for each channel → `_filtered_spectra`
3. Update spectrum preview charts
4. Compute xy, XYZ, u'v', luminance for each filtered spectrum
5. Compute white point xy (luminance-weighted mix)
6. Update CIE diagram (original + filtered + white + trajectory)
7. Update chromaticity data table
8. Update gamut result tables (1931 + 1976)
9. Update spectrum data table (Peak/FWHM/Dom.λ/Purity)
10. Emit `white_point_calculated` signal

---

## 8. Layout State Persistence

- **QSettings Key**: `"gamut_calculator_layout_v2"`
- **Save**: Called on `splitter.splitterMoved`
- **Restore**: Called at `__init__` end
- **Format**: Dict of splitter index → base64 state string
