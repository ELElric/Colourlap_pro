"""SpectrumPage — workspace page for spectrum data management."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.controllers.spectrum_controller import SpectrumController, SpectrumSummary
from colorlab_pro.dto.channels import (
    CHANNEL_OPTIONS,
)
from colorlab_pro.dto.spectrum import Spectrum
from colorlab_pro.ui.viewmodels.spectrum_viewmodel import SpectrumViewModel
from colorlab_pro.ui.widgets.spectrum_chart import SpectrumChartWidget

# Supported file extensions for import
_IMPORT_FILE_FILTER = "Spectrum Files (*.csv *.xlsx *.txt);;All Files (*)"
_IMPORT_EXTENSIONS = (".csv", ".xlsx", ".txt")
_CATEGORIES = ["LED", "CF", "QD", "白光"]

# Channel color mapping for badges
_CHANNEL_COLORS = {
    "R": {"bg": "#4a2020", "fg": "#ff6666"},
    "G": {"bg": "#204a20", "fg": "#66ff66"},
    "B": {"bg": "#20204a", "fg": "#6666ff"},
    "W": {"bg": "#3a3a3a", "fg": "#ffffff"},
}

# Category badge styling
_CATEGORY_STYLES = {
    "LED": {"bg": "#3a3a2a", "fg": "#ffd700", "border": "#555500"},
    "CF": {"bg": "#2a3a3a", "fg": "#4fc3f7", "border": "#005555"},
    "QD": {"bg": "#3a2a3a", "fg": "#e040e0", "border": "#550055"},
    "白光": {"bg": "#3a3a3a", "fg": "#ffffff", "border": "#555555"},
}


class SpectrumPage(QWidget):
    """Workspace page for importing, viewing, and analyzing spectra.

    Supports drag-and-drop CSV/XLSX import, multi-select batch operations,
    and right-click context menu (Rename / Duplicate / Delete / Export).
    """

    def __init__(
        self,
        controller: SpectrumController,
        page_index: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize with a SpectrumController.

        Args:
            controller: The spectrum controller for data operations.
            page_index: The index of this page in the stacked widget.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._controller = controller
        self._page_index = page_index
        self._view_model = SpectrumViewModel(controller, parent=self)
        self._dirty = True  # Data needs refresh on first show
        self._build_ui()
        self._wire_signals()
        self._setup_drag_drop()
        self._setup_context_menu()
        self._setup_shortcuts()

    def _build_ui(self) -> None:
        """Construct the page layout with improved UI design."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── Page Header ──
        header_layout = QHBoxLayout()
        title_label = QLabel("📊 Spectrum Page")
        title_label.setStyleSheet("color: #4fc3f7; font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # ── Toolbar with Search & Filters ──
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background: #252526;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)

        # Search box
        search_container = QFrame()
        search_container.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 4, 8, 4)
        search_layout.setSpacing(6)
        
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("color: #888; font-size: 14px;")
        search_layout.addWidget(search_icon)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search spectra by name...")
        self._search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #e0e0e0;
                font-size: 12px;
            }
            QLineEdit::placeholder {
                color: #666;
            }
        """)
        search_layout.addWidget(self._search_input)
        toolbar_layout.addWidget(search_container)

        # Category filter
        filter_label = QLabel("Category:")
        filter_label.setStyleSheet("color: #999; font-size: 11px;")
        toolbar_layout.addWidget(filter_label)
        
        self._category_filter = QComboBox()
        self._category_filter.addItems(["All"] + _CATEGORIES)
        self._category_filter.setStyleSheet("""
            QComboBox {
                background: #1e1e1e;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #e0e0e0;
                font-size: 11px;
                min-width: 80px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888;
            }
        """)
        toolbar_layout.addWidget(self._category_filter)

        # Channel filter
        ch_label = QLabel("Channel:")
        ch_label.setStyleSheet("color: #999; font-size: 11px;")
        toolbar_layout.addWidget(ch_label)
        
        self._channel_filter = QComboBox()
        self._channel_filter.addItems(["All", "R", "G", "B", "W"])
        self._channel_filter.setStyleSheet("""
            QComboBox {
                background: #1e1e1e;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #e0e0e0;
                font-size: 11px;
                min-width: 60px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888;
            }
        """)
        toolbar_layout.addWidget(self._channel_filter)

        toolbar_layout.addStretch()

        # Action buttons
        self._import_btn = QPushButton("📥 Import")
        self._import_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                border: 1px solid #0078d4;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #1a8ae8;
            }
        """)
        
        self._export_btn = QPushButton("📤 Export")
        self._export_btn.setStyleSheet("""
            QPushButton {
                background: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #4a4a4a;
            }
        """)
        
        self._delete_btn = QPushButton("🗑 Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.setToolTip("Select spectra first to delete")
        self._delete_btn.setStyleSheet("""
            QPushButton {
                background: #a02020;
                color: white;
                border: 1px solid #a02020;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:disabled {
                background: #a02020;
                opacity: 0.5;
            }
            QPushButton:enabled:hover {
                background: #c03030;
            }
        """)
        
        toolbar_layout.addWidget(self._import_btn)
        toolbar_layout.addWidget(self._export_btn)
        toolbar_layout.addWidget(self._delete_btn)
        
        layout.addWidget(toolbar)

        # ── Main horizontal splitter: table | right panel ──
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(6)

        # -- Left: spectrum table --
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Table header with count
        table_header = QHBoxLayout()
        table_title = QLabel("Spectrum List")
        table_title.setStyleSheet("color: #4fc3f7; font-weight: bold; font-size: 13px;")
        table_header.addWidget(table_title)
        table_header.addStretch()
        self._table_count_label = QLabel("0 spectra")
        self._table_count_label.setStyleSheet("color: #888; font-size: 11px;")
        table_header.addWidget(self._table_count_label)
        left_layout.addLayout(table_header)

        # Table - 7 columns (removed Source and Created)
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["", "Name", "Category", "Channel", "Peak (nm)", "FWHM (nm)", "Thickness (μm)"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 32)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        # Allow Name column (1) to be edited by double-click
        self._table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        # Prevent the checkbox column (0) from being sorted
        self._table.horizontalHeader().setSectionsClickable(True)
        self._table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        
        # Apply table styling
        self._table.setStyleSheet("""
            QTableWidget {
                background: #252526;
                border: 1px solid #444;
                border-radius: 6px;
                gridline-color: #333;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333;
            }
            QTableWidget::item:selected {
                background: #1a3a5c;
            }
            QHeaderView::section {
                background: #2d2d2d;
                color: #4fc3f7;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #444;
                font-weight: normal;
            }
        """)
        left_layout.addWidget(self._table)

        # -- Right: chart + info (vertical splitter) --
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # Chart panel
        chart_panel = QFrame()
        chart_panel.setStyleSheet("""
            QFrame {
                background: #252526;
                border: 1px solid #444;
                border-radius: 6px;
            }
        """)
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(0)

        self._preview_tabs = QTabWidget()
        self._preview_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #252526;
            }
            QTabBar::tab {
                background: #252526;
                color: #888;
                padding: 10px 16px;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #fff;
                border-bottom-color: #0078d4;
            }
            QTabBar::tab:hover {
                color: #e0e0e0;
            }
        """)

        self._original_tab = QWidget()
        orig_layout = QVBoxLayout(self._original_tab)
        orig_layout.setContentsMargins(8, 8, 8, 8)
        self._chart_original = SpectrumChartWidget()
        self._chart_original.setStyleSheet("background: #1a1a1a; border-radius: 4px;")
        orig_layout.addWidget(self._chart_original)
        self._preview_tabs.addTab(self._original_tab, "📈 Original")

        self._normalized_tab = QWidget()
        norm_layout = QVBoxLayout(self._normalized_tab)
        norm_layout.setContentsMargins(8, 8, 8, 8)
        self._chart_normalized = SpectrumChartWidget()
        self._chart_normalized.setStyleSheet("background: #1a1a1a; border-radius: 4px;")
        norm_layout.addWidget(self._chart_normalized)
        self._preview_tabs.addTab(self._normalized_tab, "📊 Normalized")

        self._preview_tabs.setCurrentIndex(1)
        chart_layout.addWidget(self._preview_tabs)
        right_layout.addWidget(chart_panel, stretch=3)

        # Info panel - Card style
        info_panel = QFrame()
        info_panel.setStyleSheet("""
            QFrame {
                background: #252526;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(10)

        # Info header
        info_header = QHBoxLayout()
        info_title = QLabel("Spectrum Info")
        info_title.setStyleSheet("color: #4fc3f7; font-weight: bold; font-size: 13px;")
        info_header.addWidget(info_title)
        info_header.addStretch()
        self._selection_count_badge = QLabel("0 selected")
        self._selection_count_badge.setStyleSheet("""
            QLabel {
                background: #264f78;
                color: #4fc3f7;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 10px;
            }
        """)
        self._selection_count_badge.setVisible(False)
        info_header.addWidget(self._selection_count_badge)
        info_layout.addLayout(info_header)

        # Info cards grid
        info_grid = QGridLayout()
        info_grid.setSpacing(8)

        # Create info cards
        self._info_cards = {}
        card_definitions = [
            ("xy", "CIE 1931 xy", "#4fc3f7", "color-xy"),
            ("u'v'", "CIE 1976 u'v'", "#81d4fa", "color-uv"),
            ("Peak", "Peak Wavelength", "#ffd700", "color-peak"),
            ("FWHM", "FWHM", "#ff8a65", "color-fwhm"),
            ("Dominant λ", "Dominant λ", "#e040e0", "color-dom"),
            ("Purity", "Purity", "#66bb6a", "color-purity"),
        ]

        for i, (key, label, color, icon_class) in enumerate(card_definitions):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #1e1e1e;
                    border: 1px solid #333;
                    border-radius: 4px;
                    padding: 10px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(6)

            # Card header with colored dot
            card_header = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 8px;")
            card_header.addWidget(dot)
            
            card_label = QLabel(label)
            card_label.setStyleSheet("color: #888; font-size: 11px;")
            card_header.addWidget(card_label)
            card_header.addStretch()
            card_layout.addLayout(card_header)

            # Card value
            value_label = QLabel("-")
            value_label.setStyleSheet("color: #e0e0e0; font-size: 16px; font-weight: 500;")
            card_layout.addWidget(value_label)

            self._info_cards[key] = value_label
            
            # Add to grid (2 columns)
            row = i // 2
            col = i % 2
            info_grid.addWidget(card, row, col)

        info_layout.addLayout(info_grid)
        right_layout.addWidget(info_panel, stretch=1)

        self._splitter.addWidget(left_widget)
        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 3)
        layout.addWidget(self._splitter, stretch=1)

        # ── Bottom Status Bar ──
        status_bar = QFrame()
        status_bar.setStyleSheet("""
            QFrame {
                background: #252526;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 8, 12, 8)
        
        self._status_label = QLabel("✅ Ready")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self._status_label)
        
        status_layout.addStretch()
        
        self._status_total = QLabel("Total: 0 spectra")
        self._status_total.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self._status_total)
        
        self._status_selected = QLabel("Selected: 0")
        self._status_selected.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self._status_selected)
        
        layout.addWidget(status_bar)

    def _wire_signals(self) -> None:
        """Connect UI signals to ViewModel actions."""
        self._import_btn.clicked.connect(self._on_import)
        self._export_btn.clicked.connect(self._on_export_selected)
        self._delete_btn.clicked.connect(self._on_delete)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._preview_tabs.currentChanged.connect(self._on_preview_tab_changed)
        self._view_model.spectrum_list_changed.connect(self._on_spectrum_list_changed)
        self._view_model.selection_changed.connect(self._on_selection_changed_vm)
        self._view_model.analysis_updated.connect(self._on_analysis_updated)
        self._view_model.error_occurred.connect(
            lambda msg: self._status_label.setText(f"❌ Error: {msg}")
        )
        self._view_model.status_changed.connect(lambda msg: self._status_label.setText(msg))
        
        # Search and filter signals
        self._search_input.textChanged.connect(self._on_filter_changed)
        self._category_filter.currentTextChanged.connect(self._on_filter_changed)
        self._channel_filter.currentTextChanged.connect(self._on_filter_changed)

    def _on_spectrum_list_changed(self) -> None:
        """Handle spectrum list changes — refresh table and mark dirty."""
        self._dirty = True
        self._refresh_table()

    def _on_filter_changed(self) -> None:
        """Handle search/filter changes."""
        self._refresh_table()

    # ------------------------------------------------------------------ #
    # Drag & Drop
    # ------------------------------------------------------------------ #

    def _setup_drag_drop(self) -> None:
        """Enable drag-and-drop file import."""
        self.setAcceptDrops(True)
        self._table.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        """Accept drag events with supported spectrum files."""
        mime = event.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            if any(u.toLocalFile().lower().endswith(_IMPORT_EXTENSIONS) for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        """Handle dropped spectrum files with category selection."""
        paths = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in _IMPORT_EXTENSIONS:
                paths.append(path)
        if paths:
            self._import_files_with_category(paths)
        event.acceptProposedAction()

    # ------------------------------------------------------------------ #
    # Context Menu
    # ------------------------------------------------------------------ #

    def _setup_context_menu(self) -> None:
        """Context menu is handled via customContextMenuRequested signal."""

    def _show_context_menu(self, pos) -> None:
        """Show right-click context menu on table rows."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return

        menu_pos = self._table.viewport().mapToGlobal(pos)
        ctx = QMenu(self)

        if len(rows) == 1:
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(self._on_rename)
            ctx.addAction(rename_action)

            dup_action = QAction("Duplicate", self)
            dup_action.triggered.connect(self._on_duplicate)
            ctx.addAction(dup_action)

        export_action = QAction("Export Selected", self)
        export_action.triggered.connect(self._on_export_selected)
        ctx.addAction(export_action)

        ctx.addSeparator()

        del_action = QAction("Delete", self)
        del_action.triggered.connect(self._on_delete)
        ctx.addAction(del_action)

        ctx.exec(menu_pos)

    def _on_rename(self) -> None:
        """Rename the selected spectrum (single selection only)."""
        info = self._view_model.selected_spectrum
        if info is None:
            return
        from PySide6.QtWidgets import QInputDialog

        new_name, ok = QInputDialog.getText(self, "Rename Spectrum", "New name:", text=info.name)
        if ok and new_name.strip():
            self._view_model.rename_spectrum(info.id, new_name.strip())

    def _on_duplicate(self) -> None:
        """Duplicate the selected spectrum (single selection only)."""
        info = self._view_model.selected_spectrum
        if info is None:
            return
        self._view_model.duplicate_spectrum(info.id)

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def _on_export_selected(self) -> None:
        """Export selected spectra to CSV."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        from PySide6.QtWidgets import QFileDialog

        path_str, _ = QFileDialog.getSaveFileName(self, "Export Spectra", "", "CSV (*.csv)")
        if not path_str:
            return
        count = 0
        for row in rows:
            item = self._table.item(row.row(), 1)  # Name column
            if item is not None:
                sid = item.data(Qt.ItemDataRole.UserRole)
                spec = self._controller.get_spectrum(sid)
                if spec is not None:
                    suffix = f"_{count}" if len(rows) > 1 else ""
                    out = Path(path_str).parent / f"{Path(path_str).stem}{suffix}.csv"
                    from colorlab_pro.exporters.csv_exporter import export_spectrum

                    export_spectrum(spec, out)
                    count += 1
        self._status_label.setText(f"📤 Exported {count} spectrum(ies).")

    # ------------------------------------------------------------------ #
    # Auto-refresh
    # ------------------------------------------------------------------ #

    def connect_auto_refresh(self, window) -> None:
        """Connect to MainWindow.page_about_to_show for auto-refresh on page switch."""
        window.page_about_to_show.connect(self._on_page_show)

    def _on_page_show(self, page_index: int) -> None:
        """Auto-refresh when this page becomes visible (only if dirty)."""
        if page_index == self._page_index and self._dirty:
            self.refresh()

    # ------------------------------------------------------------------ #
    # Inline editing helpers
    # ------------------------------------------------------------------ #

    def _on_category_combo_changed(self, new_category: str) -> None:
        """Handle Category combo box change in the table."""
        combo = self.sender()
        if combo is None:
            return
        sid = combo.property("spectrum_id")
        if sid is not None:
            self._controller.update_category(sid, new_category)

    def _on_channel_combo_changed(self, index: int) -> None:
        """Handle Channel combo box change in the table."""
        combo = self.sender()
        if combo is None:
            return
        sid = combo.property("spectrum_id")
        if sid is None:
            return
        _, value = CHANNEL_OPTIONS[index]
        if value is None:
            # Auto-detect
            spec = self._controller.get_spectrum(sid)
            if spec is None:
                return
            value = self._controller.detect_channel(spec)
        self._view_model.update_channel(sid, value)

    # ------------------------------------------------------------------ #
    # Import (unified)
    # ------------------------------------------------------------------ #

    def _on_import(self) -> None:
        """Open a file dialog for unified spectrum import."""
        from pathlib import Path as _Path

        from PySide6.QtWidgets import QFileDialog

        paths_str, _ = QFileDialog.getOpenFileNames(
            self, "Import Spectrum", "", _IMPORT_FILE_FILTER
        )
        if not paths_str:
            return

        paths = [_Path(p) for p in paths_str]
        self._import_files_with_category(paths)

    def _import_files_with_category(self, paths: list[Path]) -> None:
        """Show category selection dialog, then import the given files."""
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        category, ok = QInputDialog.getItem(
            self,
            "Select Category",
            "Category:",
            _CATEGORIES,
            0,
            False,
        )
        if not ok:
            return

        imported_count = 0
        for path in paths:
            result = self._view_model.import_file(path, category=category)
            if result is not None:
                if isinstance(result, list):
                    imported_count += len(result)
                else:
                    imported_count += 1

        if imported_count == 0:
            QMessageBox.warning(
                self,
                "Import Failed",
                "Failed to import spectra.\n\n"
                "Make sure a project is selected. "
                "Check the status bar at the bottom for details.",
            )
        else:
            self._status_label.setText(f"📥 Imported {imported_count} spectrum(ies).")

    def _on_delete(self) -> None:
        """Delete selected spectra after confirmation."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        count = len(rows)
        reply = QMessageBox.warning(
            self,
            "Delete Spectra",
            f"Are you sure you want to delete {count} spectrum(ies)?\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Collect all sids first, then delete — deleting one-by-one
            # triggers table refresh which invalidates remaining row indices.
            sids = []
            for row in rows:
                item = self._table.item(row.row(), 1)  # Name column
                if item is not None:
                    sid = item.data(Qt.ItemDataRole.UserRole)
                    sids.append(sid)
            for sid in sids:
                self._view_model.delete_spectrum(sid)

    def _on_selection_changed(self) -> None:
        """Handle table row selection."""
        rows = self._table.selectionModel().selectedRows()
        count = len(rows)
        self._delete_btn.setEnabled(count > 0)
        self._selection_count_badge.setVisible(count > 0)
        self._selection_count_badge.setText(f"{count} selected")
        self._status_selected.setText(f"Selected: {count}")
        
        if rows:
            row = rows[0].row()
            item = self._table.item(row, 1)  # Name column (col 1) holds UserRole data
            if item is not None:
                sid = item.data(Qt.ItemDataRole.UserRole)
                self._view_model.select_spectrum(sid)

    def _on_selection_changed_vm(self, info: SpectrumSummary | None) -> None:
        """Update UI when ViewModel selection changes. Auto-trigger analysis + chart."""
        if info is not None:
            self._status_label.setText(f"Selected: {info.name}")
            self._view_model.analyze(info.id)
        else:
            self._status_label.setText("✅ Ready")
            self._clear_info_panel()

        # Update charts for all selected rows (multi-select overlay)
        self._update_charts_for_selection()

    def _on_analysis_updated(self, result: dict) -> None:
        """Display analysis results including CCT, u'v', dominant wavelength."""
        self._update_info_panel(result)

    def _on_cell_changed(self, row: int, col: int) -> None:
        """Handle cell changes — Name edits with confirmation, checkbox updates."""
        if col == 0:  # Checkbox column
            self._update_charts_for_selection()
        elif col == 1:  # Name column — confirm rename
            self._handle_name_edit(row)

    def _on_header_clicked(self, logical_index: int) -> None:
        """Handle header click. The checkbox column (0) is not sortable.

        If the user clicks on column 0, revert the sort indicator to the
        previous sort column to prevent checkbox column sorting.
        """
        if logical_index == 0:
            header = self._table.horizontalHeader()
            # Revert to the last non-zero sort column/direction
            prev_col = getattr(self, "_last_sort_col", 1)
            prev_order = getattr(self, "_last_sort_order", Qt.SortOrder.AscendingOrder)
            header.setSortIndicator(prev_col, prev_order)
        else:
            # Remember the sort column and direction for future reverts
            header = self._table.horizontalHeader()
            self._last_sort_col = logical_index
            self._last_sort_order = header.sortIndicatorOrder()

    def _handle_name_edit(self, row: int) -> None:
        """Show confirmation dialog when a Name cell is edited."""
        name_item = self._table.item(row, 1)
        if name_item is None:
            return
        sid = name_item.data(Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        new_name = name_item.text().strip()
        if not new_name:
            return

        reply = QMessageBox.question(
            self,
            "Rename Spectrum",
            f"Rename to '{new_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._view_model.rename_spectrum(sid, new_name)
        else:
            # Revert to original name
            self._table.blockSignals(True)
            for s in self._view_model.spectra:
                if s.id == sid:
                    name_item.setText(s.name)
                    break
            self._table.blockSignals(False)

    def _refresh_table(self) -> None:
        """Populate the table from ViewModel data with filters applied."""
        spectra = self._view_model.spectra
        
        # Apply filters
        search_text = self._search_input.text().lower().strip()
        category_filter = self._category_filter.currentText()
        channel_filter = self._channel_filter.currentText()
        
        filtered_spectra = []
        for s in spectra:
            # Search filter
            if search_text and search_text not in s.name.lower():
                continue
            # Category filter
            if category_filter != "All" and s.category != category_filter:
                continue
            # Channel filter
            if channel_filter != "All" and s.channel != channel_filter:
                continue
            filtered_spectra.append(s)
        
        # Save current selection before rebuild
        selected_sid = None
        if self._view_model.selected_spectrum is not None:
            selected_sid = self._view_model.selected_spectrum.id

        self._table.blockSignals(True)
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(filtered_spectra))
        
        for row, s in enumerate(filtered_spectra):
            # Column 0: Checkbox
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            cb_item.setCheckState(Qt.CheckState.Unchecked)
            cb_item.setData(Qt.ItemDataRole.UserRole, s.id)
            self._table.setItem(row, 0, cb_item)

            # Column 1: Name (editable)
            name_item = QTableWidgetItem(s.name)
            name_item.setData(Qt.ItemDataRole.UserRole, s.id)
            name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 1, name_item)

            # Column 2: Category (dropdown with badge styling)
            cat_combo = QComboBox()
            cat_combo.setObjectName("table-combo")
            cat_combo.addItems(_CATEGORIES)
            current_cat = s.category or _CATEGORIES[0]
            if current_cat in _CATEGORIES:
                cat_combo.setCurrentText(current_cat)
            cat_combo.setProperty("spectrum_id", s.id)
            cat_combo.currentTextChanged.connect(self._on_category_combo_changed)
            self._table.setCellWidget(row, 2, cat_combo)

            # Column 3: Channel (dropdown)
            ch_combo = QComboBox()
            ch_combo.setObjectName("table-combo")
            for label, _ in CHANNEL_OPTIONS:
                ch_combo.addItem(label)
            current_ch = s.channel or "-"
            # Find matching option
            for i, (label, value) in enumerate(CHANNEL_OPTIONS):
                if value == current_ch or (value is None and current_ch == "-"):
                    ch_combo.setCurrentIndex(i)
                    break
            ch_combo.setProperty("spectrum_id", s.id)
            ch_combo.currentIndexChanged.connect(self._on_channel_combo_changed)
            self._table.setCellWidget(row, 3, ch_combo)

            # Column 4: Peak wavelength (integer, no decimals)
            peak_str = f"{s.peak_wavelength:.0f}" if s.peak_wavelength is not None else "-"
            peak_item = QTableWidgetItem(peak_str)
            peak_item.setFlags(peak_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 4, peak_item)

            # Column 5: FWHM (only for LED/QD, integer, no decimals)
            fwhm_str = "-"
            if s.category in ("LED", "QD") and s.fwhm is not None:
                fwhm_str = f"{s.fwhm:.0f}"
            fwhm_item = QTableWidgetItem(fwhm_str)
            fwhm_item.setFlags(fwhm_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 5, fwhm_item)

            # Column 6: Thickness (2 decimal places)
            if s.thickness_um is not None:
                thickness_str = f"{s.thickness_um:.2f}"
            elif s.thickness_missing:
                thickness_str = "缺失"
            else:
                thickness_str = "-"
            thickness_item = QTableWidgetItem(thickness_str)
            thickness_item.setFlags(thickness_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 6, thickness_item)

        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

        # Update count labels
        total_count = len(spectra)
        filtered_count = len(filtered_spectra)
        self._table_count_label.setText(f"{filtered_count} spectra")
        self._status_total.setText(f"Total: {total_count} spectra")

        # Restore selection after table rebuild (while signals are still
        # blocked to avoid triggering unnecessary re-analysis)
        if selected_sid is not None:
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 1)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_sid:
                    self._table.selectRow(row)
                    break

        self._table.blockSignals(False)
        self._table.viewport().update()

    # ------------------------------------------------------------------ #
    # Shortcuts
    # ------------------------------------------------------------------ #

    def _setup_shortcuts(self) -> None:
        """Register keyboard shortcuts."""
        # No shortcuts currently

    # ------------------------------------------------------------------ #
    # Preview Tab
    # ------------------------------------------------------------------ #

    def _on_preview_tab_changed(self, index: int) -> None:
        """Handle preview tab switch — re-plot the current selection."""
        self._update_charts_for_selection()

    def _update_charts_for_selection(self) -> None:
        """Plot all selected spectra on both original and normalized charts."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._chart_original.clear()
            self._chart_normalized.clear()
            return

        # Channel color map
        channel_colors = {
            "R": "#FF4444",
            "G": "#44FF44",
            "B": "#4488FF",
        }
        default_color = "#4FC3F7"

        spectra_data: list[tuple[str, Spectrum, str]] = []
        for row_index in rows:
            item = self._table.item(row_index.row(), 1)  # Name column
            if item is not None:
                sid = item.data(Qt.ItemDataRole.UserRole)
                spec = self._controller.get_spectrum(sid)
                if spec is not None:
                    name = item.text()
                    # Get channel from meta for color
                    channel = spec.meta.get("channel") if spec.meta else None
                    color = channel_colors.get(channel, default_color)
                    spectra_data.append((name, spec, color))

        if not spectra_data:
            self._chart_original.clear()
            self._chart_normalized.clear()
            return

        # Plot original spectra
        self._chart_original.clear()
        for name, spec, color in spectra_data:
            self._chart_original.plot_spectrum(spec, label=name, color=color)

        # Plot normalized spectra
        self._chart_normalized.clear()
        for name, spec, color in spectra_data:
            norm_values = self._normalize_spectrum(spec.values)
            from colorlab_pro.dto.spectrum import Spectrum as SpectrumDTO

            norm_spec = SpectrumDTO(
                wavelengths=spec.wavelengths.copy(),
                values=norm_values,
                unit="normalized",
                meta=spec.meta,
            )
            self._chart_normalized.plot_spectrum(norm_spec, label=name, color=color)

    @staticmethod
    def _normalize_spectrum(values: np.ndarray) -> np.ndarray:
        """Peak normalization: values / max(values)."""
        if values.size == 0:
            return values.copy()
        max_val = np.max(values)
        if max_val > 0:
            return values / max_val
        return values.copy()

    # ------------------------------------------------------------------ #
    # Spectrum Info Panel
    # ------------------------------------------------------------------ #

    def _update_info_panel(self, result: dict) -> None:
        """Update the spectrum info panel from analysis results.

        Visibility rules by category:
        - LED/QD: show Peak, Dominant λ, FWHM, Purity
        - RGB/CF (and others): show xy, u'v'
        """
        info = self._view_model.selected_spectrum
        # Guard against mismatch between result and current selection
        result_sid = result.get("spectrum_id")
        if info is not None and result_sid is not None and info.id != result_sid:
            return  # Result doesn't match current selection, skip update
        spec = None
        if info is not None:
            spec = self._controller.get_spectrum(info.id)

        category = info.category if info is not None else None
        show_shape = category in ("LED", "QD")

        # xy
        xy_val = result.get("xy")
        if xy_val is not None:
            self._info_cards["xy"].setText(f"({xy_val.x:.3f}, {xy_val.y:.3f})")
        else:
            self._info_cards["xy"].setText("-")

        # u'v'
        upv = result.get("uprime_vprime")
        if upv is not None:
            self._info_cards["u'v'"].setText(f"({upv[0]:.3f}, {upv[1]:.3f})")
        else:
            self._info_cards["u'v'"].setText("-")

        # Peak
        peak_wl = None
        if spec is not None and show_shape and spec.values.size > 0:
            peak_idx = int(np.argmax(spec.values))
            peak_wl = float(spec.wavelengths[peak_idx])
        self._info_cards["Peak"].setText(f"{peak_wl:.0f} nm" if peak_wl is not None else "-")

        # FWHM
        fwhm = self._compute_fwhm(spec) if spec is not None and show_shape else None
        self._info_cards["FWHM"].setText(f"{fwhm:.0f} nm" if fwhm is not None else "-")

        # Dominant λ
        dom_wl = result.get("dominant_wavelength") if show_shape else None
        self._info_cards["Dominant λ"].setText(f"{dom_wl:.0f} nm" if dom_wl is not None else "-")

        # Purity — now computed in the Service layer (background thread)
        purity = result.get("purity") if show_shape else None
        self._info_cards["Purity"].setText(f"{purity:.3f}" if purity is not None else "-")

    def _clear_info_panel(self) -> None:
        """Reset all info panel labels to dash."""
        for label in self._info_cards.values():
            label.setText("-")

    @staticmethod
    def _compute_fwhm(spec: Spectrum) -> float | None:
        """Compute Full Width at Half Maximum for a spectrum.

        Finds the peak, then searches left and right for where the value
        drops to half the peak value. Uses linear interpolation at the
        half-max crossings for better accuracy.
        """
        values = spec.values
        wavelengths = spec.wavelengths
        if values.size < 3:
            return None

        peak_val = float(np.max(values))
        if peak_val <= 0:
            return None

        half_max = peak_val / 2.0
        peak_idx = int(np.argmax(values))

        # Search left from peak
        left_wl = None
        for i in range(peak_idx - 1, -1, -1):
            if values[i] < half_max:
                # Linear interpolation
                if i + 1 < values.size:
                    frac = (half_max - values[i]) / (values[i + 1] - values[i])
                    left_wl = wavelengths[i] + frac * (wavelengths[i + 1] - wavelengths[i])
                else:
                    left_wl = wavelengths[i]
                break

        # Search right from peak
        right_wl = None
        for i in range(peak_idx + 1, values.size):
            if values[i] < half_max:
                # Linear interpolation
                frac = (half_max - values[i - 1]) / (values[i] - values[i - 1])
                right_wl = wavelengths[i - 1] + frac * (wavelengths[i] - wavelengths[i - 1])
                break

        if left_wl is not None and right_wl is not None:
            return float(right_wl - left_wl)
        return None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Trigger a data refresh."""
        self._dirty = False
        self._view_model.refresh()
