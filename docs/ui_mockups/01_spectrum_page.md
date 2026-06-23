# 01 - Spectrum Page

`spectrum_page.py` | Class: `SpectrumPage(QWidget)` | ~858 lines

Workspace page for importing, viewing, and analyzing spectra. Supports drag-and-drop CSV/XLSX import, multi-select batch operations, and right-click context menu.

---

## 1. Layout Hierarchy (Widget Tree)

```
QVBoxLayout outer_layout
├── QHBoxLayout toolbar
│   ├── QLabel("<h3>Spectra</h3>")
│   ├── QPushButton _import_btn          text="Import"
│   ├── QPushButton _export_btn          text="Export"
│   └── QPushButton _delete_btn          text="Delete", enabled=False
├── QHBoxLayout status_bar
│   └── QLabel _status_label             text=""
└── QSplitter(H) _splitter               handleWidth=6
    ├── QWidget [Left Panel]
    │   └── QVBoxLayout
    │       └── QTableWidget _table       0 rows, 9 cols
    └── QWidget [Right Panel]
        └── QVBoxLayout
            ├── QTabWidget _preview_tabs   current=1
            │   ├── Tab "Original"
            │   │   └── SpectrumChartWidget _chart_original
            │   └── Tab "Normalized"
            │       └── SpectrumChartWidget _chart_normalized
            └── QGroupBox("Spectrum Info")
                └── QVBoxLayout
                    ├── QWidget _color_info_widget
                    │   └── QGridLayout
                    │       ├── QLabel("<b>xy:</b>") + QLabel _info_labels["xy"]  text="-"
                    │       └── QLabel("<b>u'v':</b>") + QLabel _info_labels["u'v'"]  text="-"
                    └── QWidget _shape_info_widget
                        └── QGridLayout
                            ├── QLabel("<b>Peak:</b>") + QLabel _info_labels["Peak"]  text="-"
                            ├── QLabel("<b>Dominant λ:</b>") + QLabel _info_labels["Dominant λ"]  text="-"
                            ├── QLabel("<b>FWHM:</b>") + QLabel _info_labels["FWHM"]  text="-"
                            └── QLabel("<b>Purity:</b>") + QLabel _info_labels["Purity"]  text="-"
```

---

## 2. Visual Mockup

```
┌──────────────────────────────────────────────────────────────────────┐
│  Spectra                                               [Import] [Export] [Delete] │
├─────────────────────────────────────┬────────────────────────────────┤
│  ☐  Name          Category Channel  │  [Original] [Normalized]      │
│  ☐  LED_R_630nm   [LED▾]  [R▾]     │  ┌──────────────────────────┐ │
│  ☐  CF_Red_1um    [CF▾]   [R▾]     │  │                          │ │
│      Peak  FWHM  Thickness Source Created │  │    Spectrum Chart Area    │ │
│      630   20    -         Import  06-23  │  │                          │ │
│      -     -     1.0       Import  06-23  │  └──────────────────────────┘ │
│                                     │                                │
│                                     │  ┌─ Spectrum Info ───────────┐ │
│                                     │  │ xy: -     u'v': -         │ │
│                                     │  │ Peak: -   Dominant λ: -   │ │
│                                     │  │ FWHM: -   Purity: -       │ │
│                                     │  └───────────────────────────┘ │
└─────────────────────────────────────┴────────────────────────────────┘
```

---

## 3. Table Widget Specification

### _table (QTableWidget)

| Property | Value |
|----------|-------|
| columnCount | 9 |
| horizontalHeaderLabels | `["", "Name", "Category", "Channel", "Peak", "FWHM", "Thickness", "Source", "Created"]` |
| selectionBehavior | SelectRows |
| selectionMode | ExtendedSelection |
| editTriggers | DoubleClicked |
| sortingEnabled | True |
| contextMenuPolicy | CustomContextMenu |

### Column Details

| Col | Header | Width | ResizeMode | Widget Type | Notes |
|-----|--------|-------|------------|-------------|-------|
| 0 | "" | 30px | Fixed | QTableWidgetItem (checkbox) | ItemIsUserCheckable, stores spectrum ID in UserRole |
| 1 | "Name" | - | Stretch | QTableWidgetItem | Editable (DoubleClicked) |
| 2 | "Category" | - | ResizeToContents | QComboBox | Items: `["LED", "CF", "QD", "白光"]` |
| 3 | "Channel" | - | ResizeToContents | QComboBox | Items from CHANNEL_OPTIONS (e.g., `["R","G","B","W"]`) |
| 4 | "Peak" | - | ResizeToContents | QTableWidgetItem | Read-only, peak_wavelength |
| 5 | "FWHM" | - | ResizeToContents | QTableWidgetItem | Read-only, fwhm (only for LED/QD) |
| 6 | "Thickness" | - | ResizeToContents | QTableWidgetItem | Read-only, thickness_um |
| 7 | "Source" | - | ResizeToContents | QTableWidgetItem | Read-only |
| 8 | "Created" | - | ResizeToContents | QTableWidgetItem | Read-only, created_at |

---

## 4. Context Menu Actions

Right-click context menu on `_table`:

| Action | Condition | Description |
|--------|-----------|-------------|
| "Rename" | Single selection | Edit the Name cell of selected spectrum |
| "Duplicate" | Single selection | Copy selected spectrum with "(Copy)" suffix |
| "Export Selected" | 1+ selected | Export checked spectra to CSV/XLSX |
| "Delete" | 1+ selected | Confirm dialog then delete |

---

## 5. Drag and Drop Import

- `acceptDrops` = `True`
- Accepted extensions: `.csv`, `.xlsx`, `.txt`
- Import dialog filter: `"Spectrum Files (*.csv *.xlsx *.txt);;All Files (*)"`

---

## 6. Signal/Slot Connections

| Signal | Slot | Description |
|--------|------|-------------|
| `_import_btn.clicked` | `_on_import` | Open file dialog for CSV/XLSX import |
| `_export_btn.clicked` | `_on_export` | Export selected spectra |
| `_delete_btn.clicked` | `_on_delete` | Delete selected spectra |
| `_table.itemSelectionChanged` | `_on_selection_changed` | Update preview chart and info labels |
| `_table.customContextMenuRequested` | `_on_context_menu` | Show right-click context menu |
| `_table.cellChanged(row, col)` | `_on_cell_changed` | Handle inline edit (Name) and combo changes |
| `_preview_tabs.currentChanged` | `_on_tab_changed` | Switch between Original/Normalized chart |
| `dragEnterEvent` | - | Accept if URL has .csv/.xlsx/.txt extension |
| `dropEvent` | `_on_drop` | Import dropped file(s) |

---

## 7. Public API

| Method | Description |
|--------|-------------|
| `refresh_list()` | Reload table from database, preserve selection |
| `connect_auto_refresh(window)` | Connect to MainWindow.page_about_to_show signal |

---

## 8. Styling Notes (Dark Theme)

- Background: `#1e1e1e`
- Widget background: `#2d2d2d`
- Text color: `#e0e0e0`
- Accent: `#4fc3f7` (headings, selected items)
- Border: `#444`
- Chart background: `#1a1a1a`
- Table header: `#333`
