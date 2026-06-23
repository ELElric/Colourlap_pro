"""AboutDialog — dialog showing application information."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from colorlab_pro.config.settings import get_config


class AboutDialog(QDialog):
    """Non-modal dialog showing version and credits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the about dialog."""
        super().__init__(parent)
        config = get_config()
        self.setWindowTitle(f"About {config.app_name}")
        self.setFixedSize(360, 200)
        self._build_ui(config)

    def _build_ui(self, config) -> None:
        """Construct the dialog layout."""
        layout = QVBoxLayout(self)

        title = QLabel(f"<h2>{config.app_name}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel(f"Version {config.app_version}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel("A professional color science workbench.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()
