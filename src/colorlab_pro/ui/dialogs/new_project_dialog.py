"""NewProjectDialog — dialog for creating a new project."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class NewProjectDialog(QDialog):
    """Modal dialog for collecting new project name and description."""

    # Emitted with (name, description) when the user confirms.
    project_accepted = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the dialog."""
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog layout."""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("Enter project name")
        self._name_edit.setMinimumWidth(300)
        form.addRow("Name *", self._name_edit)

        self._desc_edit = QTextEdit(self)
        self._desc_edit.setPlaceholderText("Optional description")
        self._desc_edit.setMaximumHeight(80)
        form.addRow("Description", self._desc_edit)

        layout.addLayout(form)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #FF6B6B;")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_accept(self) -> None:
        """Validate input and emit the project_accepted signal."""
        name = self._name_edit.text().strip()
        if not name:
            self._error_label.setText("Project name is required.")
            return

        description = self._desc_edit.toPlainText().strip() or None
        self.project_accepted.emit(name, description)
        self.accept()

    @property
    def project_name(self) -> str:
        """Return the entered project name."""
        return self._name_edit.text().strip()

    @property
    def project_description(self) -> str | None:
        """Return the entered description, or None if empty."""
        desc = self._desc_edit.toPlainText().strip()
        return desc if desc else None
