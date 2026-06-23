"""SettingsPage — workspace page for application settings."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.ui.dialogs.settings_dialog import SettingsDialog


class SettingsPage(QWidget):
    """Workspace page for application settings."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the settings page."""
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the page layout."""
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Settings</h3>"))
        header.addStretch()
        self._open_btn = QPushButton("Open Settings Dialog")
        header.addWidget(self._open_btn)
        layout.addLayout(header)

        self._info_label = QLabel(
            "Application settings are managed through the Settings dialog.\n"
            "Click the button above to open it."
        )
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        layout.addStretch()

        self._open_btn.clicked.connect(self._on_open_settings)

    def _on_open_settings(self) -> None:
        """Open the SettingsDialog."""
        dlg = SettingsDialog(self)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.open()

    def _on_settings_applied(self, settings: dict) -> None:
        """Handle settings changes — persist to disk and apply theme."""
        from colorlab_pro.config.settings import save_config

        # Persist to config file
        try:
            save_config(
                theme=settings.get("theme"),
                wavelength_start=float(settings.get("wavelength_start", 380)),
                wavelength_end=float(settings.get("wavelength_end", 780)),
                db_path=settings.get("db_path"),
            )
        except Exception as exc:
            self._info_label.setText(f"Failed to save settings: {exc}")
            return

        # Apply theme if changed
        theme = settings.get("theme", "dark")
        self._apply_theme(theme)

        self._info_label.setText(
            f"Settings saved and applied:\n"
            f"  Theme: {theme}\n"
            f"  Wavelength: {settings.get('wavelength_start', '380')}–"
            f"{settings.get('wavelength_end', '780')} nm\n"
            f"  DB Path: {settings.get('db_path', 'N/A')}"
        )

    def _apply_theme(self, theme: str) -> None:
        """Apply a theme to the application."""
        app = QApplication.instance()
        if app is None:
            return
        qss_path = Path(__file__).resolve().parent.parent / "resources" / "styles" / f"{theme}.qss"
        if qss_path.exists():
            with open(qss_path, encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        else:
            app.setStyleSheet("")
