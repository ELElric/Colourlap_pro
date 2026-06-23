"""SettingsDialog — dialog for application settings."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from colorlab_pro.config.settings import get_config


class SettingsDialog(QDialog):
    """Modal dialog for editing application settings."""

    # Emitted when settings are applied.
    settings_applied = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the dialog with current settings."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self._build_ui()
        self._load_current_settings()

    def _build_ui(self) -> None:
        """Construct the dialog layout."""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Database path
        db_row = QWidget(self)
        db_layout = QVBoxLayout(db_row)
        db_layout.setContentsMargins(0, 0, 0, 0)
        self._db_path_edit = QLineEdit(self)
        self._db_path_edit.setReadOnly(True)
        db_layout.addWidget(self._db_path_edit)
        db_browse_btn = QPushButton("Browse...")
        db_browse_btn.clicked.connect(self._browse_db_path)
        db_layout.addWidget(db_browse_btn)
        form.addRow("Database Path", db_row)

        # Theme
        self._theme_combo = QComboBox(self)
        self._theme_combo.addItems(["dark", "light"])
        form.addRow("Theme", self._theme_combo)

        # Default wavelength range
        wl_row = QWidget(self)
        wl_layout = QVBoxLayout(wl_row)
        wl_layout.setContentsMargins(0, 0, 0, 0)
        self._wl_start_edit = QLineEdit(self)
        self._wl_start_edit.setPlaceholderText("380")
        self._wl_end_edit = QLineEdit(self)
        self._wl_end_edit.setPlaceholderText("780")
        wl_layout.addWidget(self._wl_start_edit)
        wl_layout.addWidget(self._wl_end_edit)
        form.addRow("Wavelength Range (nm)", wl_row)

        # Default Observer
        self._observer_combo = QComboBox(self)
        self._observer_combo.addItems(
            [
                "CIE 1931 2 Degree Standard Observer",
                "CIE 1964 10 Degree Standard Observer",
            ]
        )
        form.addRow("Default Observer", self._observer_combo)

        # Default Illuminant
        self._illuminant_combo = QComboBox(self)
        self._illuminant_combo.addItems(["A", "C", "D50", "D55", "D65", "D75", "E"])
        form.addRow("Default Illuminant", self._illuminant_combo)

        # Default Step
        self._step_spin = QSpinBox(self)
        self._step_spin.setRange(1, 10)
        self._step_spin.setSuffix(" nm")
        self._step_spin.setSingleStep(1)
        self._step_spin.setFixedWidth(120)
        form.addRow("Default Step", self._step_spin)

        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_current_settings(self) -> None:
        """Populate fields with current config values."""
        config = get_config()
        self._db_path_edit.setText(str(config.default_db_path))
        self._theme_combo.setCurrentText(config.default_theme)
        self._wl_start_edit.setText(str(config.default_wavelength_start))
        self._wl_end_edit.setText(str(config.default_wavelength_end))
        self._observer_combo.setCurrentText(config.default_observer)
        self._illuminant_combo.setCurrentText(config.default_illuminant)
        self._step_spin.setValue(config.default_step)

    def _browse_db_path(self) -> None:
        """Open a file dialog to select the database path."""
        path_str, _ = QFileDialog.getSaveFileName(self, "Select Database Path", "", "SQLite (*.db)")
        if path_str:
            self._db_path_edit.setText(path_str)

    def _on_accept(self) -> None:
        """Collect settings, validate, and emit."""
        start_text = self._wl_start_edit.text()
        end_text = self._wl_end_edit.text()
        try:
            start = float(start_text)
            end = float(end_text)
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Wavelength Range",
                "Wavelength start and end must be valid numbers.",
            )
            return
        if not (380.0 <= start < end <= 780.0):
            QMessageBox.warning(
                self,
                "Invalid Wavelength Range",
                "Wavelength range must satisfy 380 ≤ start < end ≤ 780.",
            )
            return
        if not self._db_path_edit.text().strip():
            QMessageBox.warning(
                self,
                "Invalid Database Path",
                "Database path cannot be empty.",
            )
            return

        settings = {
            "db_path": self._db_path_edit.text(),
            "theme": self._theme_combo.currentText(),
            "wavelength_start": start_text,
            "wavelength_end": end_text,
            "default_observer": self._observer_combo.currentText(),
            "default_illuminant": self._illuminant_combo.currentText(),
            "default_step": self._step_spin.value(),
        }
        self.settings_applied.emit(settings)
        self.accept()

    def get_settings(self) -> dict:
        """Return the current dialog settings as a dict."""
        return {
            "db_path": self._db_path_edit.text(),
            "theme": self._theme_combo.currentText(),
            "wavelength_start": self._wl_start_edit.text(),
            "wavelength_end": self._wl_end_edit.text(),
            "default_observer": self._observer_combo.currentText(),
            "default_illuminant": self._illuminant_combo.currentText(),
            "default_step": self._step_spin.value(),
        }
