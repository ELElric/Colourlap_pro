"""Main application window for ColorLab Pro — sidebar navigation layout."""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.config.settings import get_config
from colorlab_pro.ui.dialogs.about_dialog import AboutDialog

# Navigation items: (icon, label)
_NAV_ITEMS: list[tuple[str, str]] = [
    ("", "Spectrum Library"),
    ("", "Gamut Calculator"),
    ("", "White Point"),
    ("", "Thickness Optimizer"),
]


class _Sidebar(QWidget):
    """Left sidebar navigation with icon buttons."""

    navigation_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        self._buttons: list[QPushButton] = []
        for idx, (_icon, label) in enumerate(_NAV_ITEMS):
            btn = QPushButton(f"{label}")
            btn.setObjectName("nav-item")
            btn.setProperty("nav_index", idx)
            btn.clicked.connect(lambda checked, i=idx: self._on_clicked(i))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        self.set_current_index(0)

    def _on_clicked(self, index: int) -> None:
        self.set_current_index(index)
        self.navigation_changed.emit(index)

    def set_current_index(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)


class TopBar(QWidget):
    """Top bar with brand and status pill."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(54)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 18, 0)

        brand = QLabel("ColorLab Pro")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        layout.addStretch()

        self._status_dot = QLabel()
        self._status_dot.setObjectName("status-dot")
        self._status_dot.setFixedSize(8, 8)
        status_pill = QHBoxLayout()
        status_pill.setSpacing(8)
        status_pill.addWidget(self._status_dot)
        status_label = QLabel("Ready")
        status_label.setObjectName("status-label")
        status_pill.addWidget(status_label)
        status_container = QWidget()
        status_container.setObjectName("status-pill")
        status_container.setLayout(status_pill)
        status_container.setFixedHeight(32)
        layout.addWidget(status_container)


class MainWindow(QMainWindow):
    """Primary application window with sidebar navigation."""

    page_about_to_show = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(get_config().app_name)
        self._build_ui()
        self._build_menu_bar()
        self._build_status_bar()
        self._load_window_state()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Top bar
        self._top_bar = TopBar()
        root_layout.addWidget(self._top_bar)

        # Body: sidebar + main content
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar navigation
        self._sidebar = _Sidebar()
        self._sidebar.navigation_changed.connect(self._on_navigation_changed)
        body_layout.addWidget(self._sidebar)

        # Main content area (stacked widget for workspace pages)
        self._stack = QStackedWidget()
        body_layout.addWidget(self._stack, 1)

        root_layout.addWidget(body, 1)

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _on_about(self) -> None:
        """Handle Help → About."""
        dlg = AboutDialog(self)
        dlg.exec()

    def _build_status_bar(self) -> None:
        status = QStatusBar(self)
        status.showMessage("Ready")
        self._status_db_label = QLabel("DB: --")
        self._status_db_label.setContentsMargins(8, 0, 8, 0)
        status.addPermanentWidget(self._status_db_label)
        self._status_spectrum_label = QLabel("Spectra: 0")
        self._status_spectrum_label.setContentsMargins(8, 0, 8, 0)
        status.addPermanentWidget(self._status_spectrum_label)
        self._status_observer_label = QLabel("Observer: --")
        self._status_observer_label.setContentsMargins(8, 0, 8, 0)
        status.addPermanentWidget(self._status_observer_label)
        self._status_illuminant_label = QLabel("Illuminant: --")
        self._status_illuminant_label.setContentsMargins(8, 0, 8, 0)
        status.addPermanentWidget(self._status_illuminant_label)
        self._status_calc_time_label = QLabel("Calc: --")
        self._status_calc_time_label.setContentsMargins(8, 0, 8, 0)
        status.addPermanentWidget(self._status_calc_time_label)
        self.setStatusBar(status)

    def update_status_bar(self, **kwargs) -> None:
        if "db_status" in kwargs and kwargs["db_status"] is not None:
            self._status_db_label.setText(f"DB: {kwargs['db_status']}")
        if "spectrum_count" in kwargs and kwargs["spectrum_count"] is not None:
            self._status_spectrum_label.setText(f"Spectra: {kwargs['spectrum_count']}")
        if "observer" in kwargs and kwargs["observer"] is not None:
            self._status_observer_label.setText(f"Observer: {kwargs['observer']}")
        if "illuminant" in kwargs and kwargs["illuminant"] is not None:
            self._status_illuminant_label.setText(f"Illuminant: {kwargs['illuminant']}")
        if "calc_time" in kwargs and kwargs["calc_time"] is not None:
            self._status_calc_time_label.setText(f"Calc: {kwargs['calc_time']}")

    def _on_navigation_changed(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self.page_about_to_show.emit(index)
            self._stack.setCurrentIndex(index)

    def add_page(self, widget: QWidget, name: str) -> int:
        idx = self._stack.addWidget(widget)
        return idx

    def set_page(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._sidebar.set_current_index(index)
            self._stack.setCurrentIndex(index)

    def _load_window_state(self) -> None:
        settings = QSettings(get_config().org_name, get_config().app_name)
        geometry = settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(QSize(1600, 900))
            self.setMinimumSize(QSize(1200, 700))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        settings = QSettings(get_config().org_name, get_config().app_name)
        settings.setValue("geometry", self.saveGeometry())
        event.accept()


def create_application(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv or [])
    return app  # type: ignore[return-value]
