"""Main application window for ColorLab Pro — sidebar navigation layout."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSettings, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
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

# Navigation items: (icon kind, label). Icons are drawn as vector pixmaps
# via _render_nav_icon so they stay crisp and consistent across platforms.
_NAV_ITEMS: list[tuple[str, str]] = [
    ("spectrum", "Spectrum Library"),
    ("gamut", "Gamut Calculator"),
    ("whitepoint", "White Point"),
    ("thickness", "Thickness Optimizer"),
]


def _render_brand_icon(color: str, size: int = 28) -> QPixmap:
    """Draw the ColorLab Pro brand icon: a stylised RGB colour disc.

    Three overlapping circles (R / G / B) that blend visually to suggest
    a colour-science tool.  Works well at small sizes and stays crisp
    because it is rendered entirely with QPainter primitives.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    c = QColor(color)
    r = size * 0.22
    offset = size * 0.12
    cx, cy = size / 2.0, size / 2.0

    for dx, dy, alpha in [(-offset, 0, 160), (0, -offset * 0.6, 130), (offset, 0, 110)]:
        rc = QColor(c)
        rc.setAlpha(alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(rc)
        painter.drawEllipse(QPointF(cx + dx, cy + dy), r, r)

    painter.end()
    return pixmap


def _render_nav_icon(kind: str, color: str, size: int = 20) -> QPixmap:
    """Draw a sidebar nav icon as a crisp vector pixmap (no font/SVG dependency).

    Each icon is centered in a ``size`` x ``size`` canvas so all four share the
    same visual weight and vertical baseline.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    center = size / 2.0
    pen = QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)

    if kind == "spectrum":
        # Smooth bell-curve wave to represent a spectrum
        path = QPainterPath()
        pts = [(0, size - 2), (3, size - 3), (5, size - 5), (7, size - 10),
               (9, size - 15), (10, size - 17), (11, size - 15), (13, size - 10),
               (15, size - 5), (17, size - 3), (20, size - 2)]
        path.moveTo(*pts[0])
        for p in pts[1:]:
            path.lineTo(*p)
        painter.drawPath(path)
    elif kind == "gamut":
        # Filled triangle representing a colour gamut
        tri = [QPointF(center, 2.5), QPointF(3, size - 3), QPointF(size - 3, size - 3)]
        c_fill = QColor(c)
        c_fill.setAlpha(48)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c_fill)
        painter.drawPolygon(QPolygonF(tri))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPolygon(QPolygonF(tri))
    elif kind == "whitepoint":
        # Crosshair + centre dot (target reticle)
        painter.drawLine(QPointF(center, 2), QPointF(center, size - 2))
        painter.drawLine(QPointF(2, center), QPointF(size - 2, center))
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(center, center), 2, 2)
    elif kind == "thickness":
        # Stacked horizontal layers (film cross-section)
        lw = size - 6
        x0 = 3
        for i, y in enumerate([4, center - 1.5, size - 5]):
            alpha = 255 - i * 50
            c_line = QColor(c)
            c_line.setAlpha(alpha)
            painter.setPen(QPen(c_line, 2.5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(x0, y), QPointF(x0 + lw, y))

    painter.end()
    return pixmap


class _NavButton(QPushButton):
    """Sidebar navigation button: a vector icon (left) + label (right)."""

    _INACTIVE_COLOR = "#8e8e93"
    _ACTIVE_COLOR = "#0a84ff"

    def __init__(self, kind: str, label: str, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self._index = index
        self.setText(label)
        self.setObjectName("nav-item")
        self.setIcon(QIcon(_render_nav_icon(kind, self._INACTIVE_COLOR)))
        self.setIconSize(QSize(20, 20))
        self.setFixedHeight(40)
        self.setProperty("active", False)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        color = self._ACTIVE_COLOR if active else self._INACTIVE_COLOR
        self.setIcon(QIcon(_render_nav_icon(self._kind, color)))
        self.style().unpolish(self)
        self.style().polish(self)


class _Sidebar(QWidget):
    """Left sidebar navigation with icon buttons."""

    navigation_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)

        # --- Brand header ---
        brand = QWidget()
        brand.setObjectName("sidebar-brand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(14, 16, 14, 16)
        brand_layout.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(_render_brand_icon("#0a84ff"))
        icon_lbl.setFixedSize(28, 28)
        name_lbl = QLabel("ColorLab Pro")
        name_lbl.setObjectName("sidebar-brand-name")
        brand_layout.addWidget(icon_lbl)
        brand_layout.addWidget(name_lbl)
        brand_layout.addStretch()
        layout.addWidget(brand)

        # Thin divider below brand
        divider = QWidget()
        divider.setObjectName("sidebar-divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        # Nav buttons
        self._buttons: list[QPushButton] = []
        for idx, (kind, label) in enumerate(_NAV_ITEMS):
            btn = _NavButton(kind, label, idx)
            btn.clicked.connect(lambda checked=False, i=idx: self._on_clicked(i))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        self.set_current_index(0)

    def _on_clicked(self, index: int) -> None:
        self.set_current_index(index)
        self.navigation_changed.emit(index)

    def set_current_index(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)


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
    theme_changed = Signal(str)

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

        view_menu = menu_bar.addMenu("&View")

        theme_menu = view_menu.addMenu("&Theme")
        self._theme_group: list[QAction] = []

        light_action = QAction("&Light", self)
        light_action.setCheckable(True)
        light_action.setData("light")
        light_action.triggered.connect(lambda: self._on_theme_changed("light"))
        theme_menu.addAction(light_action)
        self._theme_group.append(light_action)

        dark_action = QAction("&Dark", self)
        dark_action.setCheckable(True)
        dark_action.setData("dark")
        dark_action.triggered.connect(lambda: self._on_theme_changed("dark"))
        theme_menu.addAction(dark_action)
        self._theme_group.append(dark_action)

        self._sync_theme_menu(get_config().default_theme)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _on_about(self) -> None:
        """Handle Help → About."""
        dlg = AboutDialog(self)
        dlg.exec()

    def _on_theme_changed(self, theme: str) -> None:
        self._sync_theme_menu(theme)
        self.theme_changed.emit(theme)

    def _sync_theme_menu(self, theme: str) -> None:
        for action in self._theme_group:
            action.setChecked(action.data() == theme)

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
            self._update_window_title(index)

    def add_page(self, widget: QWidget, name: str) -> int:
        idx = self._stack.addWidget(widget)
        if not hasattr(self, "_page_names"):
            self._page_names: list[str] = []
        self._page_names.append(name)
        return idx

    def _update_window_title(self, index: int) -> None:
        """Update the window title to include the current page name."""
        names = getattr(self, "_page_names", [])
        if 0 <= index < len(names):
            self.setWindowTitle(f"{get_config().app_name} — {names[index]}")
        else:
            self.setWindowTitle(get_config().app_name)

    def set_page(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._sidebar.set_current_index(index)
            self._stack.setCurrentIndex(index)
            self._update_window_title(index)

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
