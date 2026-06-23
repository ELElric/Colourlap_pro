# 03 - White Point Page

`white_point_page.py` | Class: `WhitePointPage(QWidget)` | ~401 lines

White point calculation page with two modes: Forward (RGB→White) and Reverse (White→RGB ratios).

---

## 1. Layout Hierarchy (Widget Tree)

```
QVBoxLayout outer_layout
├── QGroupBox("Mode Selection")
│   └── QHBoxLayout
│       ├── QRadioButton _forward_radio    text="Forward Calculation", checked
│       ├── QRadioButton _reverse_radio    text="Reverse Calculation"
│       ├── QCheckBox _gamut_checks["sRGB"]      text="sRGB", checked
│       ├── QCheckBox _gamut_checks["NTSC"]      text="NTSC", checked
│       ├── QCheckBox _gamut_checks["DCI-P3"]    text="DCI-P3", checked
│       └── QCheckBox _gamut_checks["BT2020"]    text="BT2020", checked
│
├── QSplitter(H) row1_splitter
│   ├── QGroupBox("RGBW Input")
│   │   └── QTableWidget(4, 4) _table
│   │       Headers: ["Ch", "x", "y", "Ratio"]
│   │       Rows: R, G, B, W
│   │       Col 0: Fixed width 36 (labels only)
│   │       Col 1-3: Stretch (editable or disabled based on mode)
│   └── QGroupBox("Gamut Results")
│       └── QTableWidget(4, 5) _gamut_table
│           Headers: ["Standard", "Coverage 1931 (%)", "Match 1931 (%)",
│                     "Coverage 1976 (%)", "Match 1976 (%)"]
│           Rows: sRGB, NTSC, DCI-P3, BT2020
│           All cells: Read-only
│
└── QSplitter(H) row2_splitter
    ├── CIECanvas(mode="xy") _cie_xy_canvas  minHeight=280, ref_gamuts=[sRGB,NTSC,DCI-P3,BT2020]
    └── CIECanvas(mode="uv") _cie_uv_canvas  minHeight=280, ref_gamuts=[sRGB,NTSC,DCI-P3,BT2020]
```

---

## 2. Visual Mockup

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ┌─ Mode Selection ────────────────────────────────────────────────────┐ │
│  │  (●) Forward Calculation  ( ) Reverse Calculation                  │ │
│  │  ☑sRGB  ☑NTSC  ☑DCI-P3  ☑BT2020                                  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
├───────────────────────────────┬──────────────────────────────────────────┤
│  ┌─ RGBW Input ─────────────┐ │  ┌─ Gamut Results ────────────────────┐ │
│  │ Ch │  x     │  y     │ Ratio │  │Standard│Cov1931│Mt1931│Cov1976│Mt1976│ │
│  │ R  │ 0.640  │ 0.330  │ 0.333 │  │sRGB    │ --    │ --   │ --    │ --   │ │
│  │ G  │ 0.300  │ 0.600  │ 0.333 │  │NTSC    │ --    │ --   │ --    │ --   │ │
│  │ B  │ 0.150  │ 0.060  │ 0.333 │  │DCI-P3  │ --    │ --   │ --    │ --   │ │
│  │ W  │ 0.3127 │ 0.3290 │  -    │  │BT2020  │ --    │ --   │ --    │ --   │ │
│  └───────────────────────────┘ │  └─────────────────────────────────────┘ │
├───────────────────────────────┴──────────────────────────────────────────┤
│  ┌──────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │                          │  │                                      │  │
│  │   CIE 1931 xy Diagram    │  │   CIE 1976 u'v' Diagram             │  │
│  │                          │  │                                      │  │
│  │   [CIE图 + RGB三角形]     │  │   [CIE图 + RGB三角形]                │  │
│  │                          │  │                                      │  │
│  └──────────────────────────┘  └──────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Table Input Behavior (Mode-Dependent)

### _table Edit State by Mode

| Cell | Forward Mode | Reverse Mode |
|------|-------------|--------------|
| R/G/B x | Editable (input) | Editable (input) |
| R/G/B y | Editable (input) | Editable (input) |
| R/G/B Ratio | Editable (input) | Disabled (output) |
| W x | Disabled (output) | Editable (input) |
| W y | Disabled (output) | Editable (input) |
| W Ratio | Disabled (always) | Disabled (always) |

---

## 4. Table Specifications

### _table (RGBW Input)

| Property | Value |
|----------|-------|
| rowCount | 4 (R, G, B, W) |
| columnCount | 4 |
| horizontalHeaderLabels | `["Ch", "x", "y", "Ratio"]` |
| Col 0 width | 36px (Fixed) |
| Col 1-3 | Stretch |
| verticalHeaderVisible | False |
| selectionBehavior | SelectItems |

### _gamut_table

| Property | Value |
|----------|-------|
| rowCount | 4 (sRGB, NTSC, DCI-P3, BT2020) |
| columnCount | 5 |
| horizontalHeaderLabels | `["Standard", "Coverage 1931 (%)", "Match 1931 (%)", "Coverage 1976 (%)", "Match 1976 (%)"]` |
| All cells | Read-only (ItemIsEnabled only) |
| verticalHeaderVisible | False |

---

## 5. Signal/Slot Connections

| Signal | Slot | Description |
|--------|------|-------------|
| `_forward_radio.toggled` | `_on_mode_changed` | Toggle forward/reverse mode, update table edit states |
| `_reverse_radio.toggled` | `_on_mode_changed` | Toggle forward/reverse mode |
| `_gamut_checks.*.stateChanged` | `_on_gamut_filter_changed` | Recompute gamut results with selected standards |
| `_table.cellChanged(row, col)` | `_on_input_changed` | Recalculate white point or ratios based on mode |

---

## 6. Computation Logic

### Forward Calculation

```
Input: R/G/B x,y + R/G/B ratios (weights)
White Point: mix_xy(xy_list, weights=ratio_list)
Gamut: Build triangle from R/G/B primaries, compute coverage/match against selected standards
CIE: Plot R/G/B/W points, triangle, reference gamuts
```

### Reverse Calculation

```
Input: R/G/B x,y + Target White Point x,y
Find ratios: optimize_white_point(target_xy, primaries_xy)
Result: R/G/B ratios that produce the target white point
Gamut: Same as forward, using R/G/B primaries
```
