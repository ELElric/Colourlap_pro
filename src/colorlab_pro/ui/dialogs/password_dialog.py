"""Password dialog for PySide6 entry point.

Shares the same settings.json store as the pywebview version so passwords
are consistent across both UI entries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

_SETTINGS_FILE = Path.home() / ".colorlab_pro" / "settings.json"


def _load_settings() -> dict:
    try:
        if _SETTINGS_FILE.exists():
            return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {}


def _save_settings(data: dict) -> None:
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


class PasswordDialog(QDialog):
    """Modal password gate.

    On first run (no password set), any non-empty password >= 4 chars
    becomes the new password.  Afterwards the stored hash is compared.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ColorLab Pro — Password")
        self.setModal(True)
        self.setMinimumWidth(360)

        self._settings = _load_settings()
        self._first_run = not bool(self._settings.get("password_hash"))

        layout = QVBoxLayout(self)

        title = QLabel("Enter Password" if not self._first_run else "Set New Password")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        hint_text = (
            "Please enter the application password to continue."
            if not self._first_run
            else "First run — enter a new password (min 4 characters)."
        )
        hint = QLabel(hint_text)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._input = QLineEdit()
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        self._input.setPlaceholderText("Password")
        self._input.returnPressed.connect(self._on_submit)
        layout.addWidget(self._input)

        self._error = QLabel("")
        self._error.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        self._error.setWordWrap(True)
        layout.addWidget(self._error)

        btn = QPushButton("Unlock")
        btn.setDefault(True)
        btn.clicked.connect(self._on_submit)
        layout.addWidget(btn)

    # ------------------------------------------------------------------

    def _on_submit(self) -> None:
        pwd = self._input.text()
        if not pwd:
            return

        stored = self._settings.get("password_hash")

        if not stored:
            # First run — set password
            if len(pwd) < 4:
                self._error.setText("Password too short (min 4 chars).")
                self._input.clear()
                return
            self._settings["password_hash"] = hashlib.sha256(
                pwd.encode()
            ).hexdigest()
            _save_settings(self._settings)
            self.accept()
            return

        entered = hashlib.sha256(pwd.encode()).hexdigest()
        if entered == stored:
            self.accept()
        else:
            self._error.setText("Incorrect password. Please try again.")
            self._input.clear()
            self._input.setFocus()
