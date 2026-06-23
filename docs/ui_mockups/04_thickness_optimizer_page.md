# 04 - Thickness Optimizer Page

`thickness_optimizer_page.py` | Class: `ThicknessOptimizerPage(QWidget)` | ~1450 lines

Thickness optimization page for finding optimal color filter thicknesses. Supports coverage maximization and target white point/coordinate modes. Background thread execution with progress updates.

---

## 1. Layout Hierarchy (Widget Tree)

```
QVBoxLayout outer_layout
├── QGroupBox("Optimization Target")
│   └── QFormLayout
│       ├── Row "Target:":
│       │   └── QComboBox _target_combo
│       │       items: ["Max BT2020 Coverage", "Max DCI-P3 Coverage",
│       │               "Target White Point", "Target Coordinate"]
│       └── Row "Coordinate:" [hidden by default]:
│           └── QWidget _coord_row_widget
│               └── QHBoxLayout
│                   ├── QLabel("x:")
│                   ├── QDoubleSpinBox _target_x_spin
│                   │   range=0.0~1.0, step=0.001, decimals=4, default=0.3127, minWidth=80
│                   ├── QLabel("y:")
│                   ├── QDoubleSpinBox _target_y_spin
│                   │   range=0.0~1.0, step=0.001, decimals=4, default=0.3290, minWidth=80
│                   └── stretch
│
├── QGroupBox("Spectrum & Thickness")
│   └── QGridLayout 4 rows x 3 cols
│       ├── [0,0] QLabel("<b>RGB (Emission)</b>")
│       ├── [0,1] QLabel("<b>CF (Transmittance)</b>")
│       ├── [0,2] QLabel("<b>Range (μm)</b>")
│       ├── [1,0] _SpectrumSelector("R") -> _rgb_sel_R
│       ├── [1,1] _SpectrumSelector("RCF") -> _filter_sel_RCF
│       ├── [1,2] _ThicknessRangeControl("RCF") -> _range_RCF
│       ├── [2,0] _SpectrumSelector("G") -> _rgb_sel_G
│       ├── [2,1] _SpectrumSelector("GCF") -> _filter_sel_GCF
│       ├── [2,2] _ThicknessRangeControl("GCF") -> _range_GCF
│       ├── [3,0] _SpectrumSelector("B") -> _rgb_sel_B
│       ├── [3,1] _SpectrumSelector("BCF") -> _filter_sel_BCF
│       └── [3,2] _ThicknessRangeControl("BCF") -> _range_BCF
│
├── QHBoxLayout [Button Row]
│   ├── stretch
│   ├── QPushButton("Start Optimization") _start_btn  height=36, minWidth=200
│   ├── QPushButton("Stop") _stop_btn  height=36, minWidth=80, enabled=False
│   └── stretch
│
├── QLabel("") _status_label  AlignCenter
│
└── QWidget result_widget [stretch=1]
    └── QHBoxLayout
        ├── QGroupBox("Optimization Result") [stretch=1]
        │   └── QTableWidget(0, 13) _result_table
        │       Headers: ["Rank", "RCF (um)", "GCF (um)", "BCF (um)",
        │                "Coverage", "Match", "White Point",
        │                "R (x, y)", "G (x, y)", "B (x, y)",
        │                "R Ratio", "G Ratio", "B Ratio"]
        │       Col 0-5: ResizeToContents, Col 6-12: Stretch
        │       verticalHeaderVisible=False, editTriggers=NoEditTriggers
        │       selectionMode=SingleSelection
        └── QGroupBox("Scan Curve") [stretch=2]
            └── QTabWidget _scan_tab
                ├── Tab "Thickness vs Coverage"
                │   └── _LineChartWidget _chart_coverage
                │       title="Thickness vs Coverage"
                │       xlabel="GCF Thickness (X)", ylabel="Coverage (%)"
                ├── Tab "Thickness vs Coordinate"
                │   └── _LineChartWidget _chart_coordinate
                │       title="Thickness vs Coordinate"
                │       xlabel="GCF Thickness (X)", ylabel="Delta-xy"
                └── Tab "Thickness vs White Point"
                    └── _LineChartWidget _chart_white_point
                        title="Thickness vs White Point"
                        xlabel="GCF Thickness (X)", ylabel="White Point (x, y)"
```

---

## 2. Visual Mockup

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ┌─ Optimization Target ──────────────────────────────────────────────────┐ │
│  │  Target: [Max BT2020 Coverage ▾]                                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│  ┌─ Spectrum & Thickness ─────────────────────────────────────────────────┐ │
│  │  RGB (Emission)    │  CF (Transmittance)   │  Range (μm)              │ │
│  │  ────────────────  │  ───────────────────  │  ─────────────────────── │ │
│  │  R [▾] [Paste]    │  RCF [▾] [Paste]      │  RCF Min:[0.0] Max:[5.0] │ │
│  │  G [▾] [Paste]    │  GCF [▾] [Paste]      │  GCF Min:[0.0] Max:[5.0] │ │
│  │  B [▾] [Paste]    │  BCF [▾] [Paste]      │  BCF Min:[0.0] Max:[5.0] │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                    [ Start Optimization ]    [ Stop ]                        │
│                                                                              │
│  Optimization complete. Best coverage: 95.23% (RCF=1.2μm, GCF=0.8μm, BCF=1.5μm) │
├───────────────────────────────────┬──────────────────────────────────────────┤
│  ┌─ Optimization Result ────────┐ │  ┌─ Scan Curve ────────────────────────┐ │
│  │Rank│RCF │GCF │BCF │Cov│Match│ │  │[Thickness vs Coverage]              │ │
│  │ 1  │1.2 │0.8 │1.5 │95 │92  │ │  │                                     │ │
│  │ 2  │1.3 │0.9 │1.4 │94 │91  │ │  │  ┌─────────────────────────────┐   │ │
│  │ 3  │1.1 │0.7 │1.6 │94 │91  │ │  │  │                             │   │ │
│  └───────────────────────────────┘ │  │  │   Line Chart (3 curves)    │   │ │
│  ... (shows top 20 results)       │  │  │   RCF=red, GCF=green,      │   │ │
│                                   │  │  │   BCF=blue                 │   │ │
│                                   │  │  │                             │   │ │
│                                   │  │  └─────────────────────────────┘   │ │
│                                   │  └─────────────────────────────────────┘ │
└───────────────────────────────────┴──────────────────────────────────────────┘
```

---

## 3. Helper Component: _SpectrumSelector

`_SpectrumSelector(QWidget)` — Spectrum selector with dropdown and paste button.

| Property | Value |
|----------|-------|
| layout | QHBoxLayout, margins=0, spacing=6 |
| QLabel | text=channel, fixedWidth=36, colored |
| QComboBox | minWidth=120, SizeAdjustPolicy=AdjustToMinimumContentsLengthWithIcon |
| QPushButton("Paste") | fixedWidth=60 |
| Signal | `selectionChanged()` |

---

## 4. Helper Component: _ThicknessRangeControl

`_ThicknessRangeControl(QWidget)` — Min/max thickness range control.

| Property | Value |
|----------|-------|
| layout | QHBoxLayout, margins=0, spacing=8 |
| QLabel | text=channel, fixedWidth=36 |
| QLabel("Min:") | - |
| QDoubleSpinBox (min) | range=0.0~20.0, step=0.1, decimals=2, default=0.0, minWidth=56 |
| QLabel("Max:") | - |
| QDoubleSpinBox (max) | range=0.01~20.0, step=0.1, decimals=2, default=5.0, minWidth=56 |
| Signal | `rangeChanged(float)` |

---

## 5. Helper Component: _LineChartWidget

`_LineChartWidget(SpectrumChartWidget)` — Generic line chart for scan curves.

| Property | Value |
|----------|-------|
| Inherits | SpectrumChartWidget (pyqtgraph/mpl based) |
| Constructor | `_LineChartWidget(title, xlabel, ylabel)` |
| `plot_line(x, y, label, color, linestyle)` | Plot a generic line on the chart |
| `clear()` | Clear all plotted data and reset axes |

---

## 6. Result Table Specification

### _result_table (QTableWidget)

| Property | Value |
|----------|-------|
| columnCount | 13 |
| horizontalHeaderLabels | `["Rank", "RCF (um)", "GCF (um)", "BCF (um)", "Coverage", "Match", "White Point", "R (x, y)", "G (x, y)", "B (x, y)", "R Ratio", "G Ratio", "B Ratio"]` |
| rowCount | Dynamic (0 initially, up to 20 after optimization) |
| Col 0-5 ResizeMode | ResizeToContents |
| Col 6-12 ResizeMode | Stretch |
| verticalHeaderVisible | False |
| editTriggers | NoEditTriggers |
| selectionMode | SingleSelection |
| horizontalScrollMode | ScrollPerPixel |

---

## 7. Signal/Slot Connections

| Signal | Slot | Description |
|--------|------|-------------|
| `_target_combo.currentIndexChanged` | `_on_target_changed` | Show/hide coordinate input for Target modes |
| `_rgb_sel_R/G/B.selectionChanged` | `_on_rgb_selection_changed(ch)` | Load spectrum into cache |
| `_filter_sel_RCF/GCF/BCF.selectionChanged` | `_on_filter_selection_changed(ch)` | Load filter, auto-fill range from thickness_um |
| `_start_btn.clicked` | `_on_start_optimization` | Validate inputs, run background optimization |
| `_stop_btn.clicked` | `_on_stop_optimization` | Set `_cancelled=True` flag |
| `progress_update(str)` | `_status_label.setText` | Update status text from background thread |
| `run_in_background on_result` | `_on_optimization_complete` | Populate result table and scan curves |
| `run_in_background on_error` | `_on_optimization_error` | Show error in status label |
| `*.Paste clicked` | `_on_paste(ch, is_filter)` | Parse clipboard, import spectrum |

---

## 8. Background Execution Model

### Threading Architecture

1. Main thread reads all UI values (thread-safety snapshot)
2. `run_in_background(fn, on_result, on_error)` starts QRunnable in QThreadPool
3. Background thread runs `_run_optimization()` or `_run_coverage_scan()`
4. Progress updates via `self.progress_update.emit(str)` → queued to main thread
5. Results returned as `list[dict]` via signal → `_on_optimization_complete`
6. Scan data embedded in each result dict as `_scan_data` key (avoids cross-thread mutation)
7. Cancellation: background checks `self._cancelled` flag each iteration

---

## 9. Optimization Targets

### Target Types and Behavior

| Target | Method | Scan Range |
|--------|--------|------------|
| Max BT2020 Coverage | Channel sweep (100 steps each) | Full min→max for each channel |
| Max DCI-P3 Coverage | Channel sweep (100 steps each) | Full min→max for each channel |
| Target White Point | L-BFGS-B optimizer | Local scan ±25% around optimum (21 steps) |
| Target Coordinate | L-BFGS-B optimizer | Local scan ±25% around optimum (21 steps) |
