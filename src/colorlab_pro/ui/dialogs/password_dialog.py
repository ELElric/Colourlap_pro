"""Password gate dialog for ColorLab Pro.

Blocks application entry until the correct password is provided.
Supports password setting on first use and verification on subsequent runs.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# File that stores the hashed password (never the plaintext).
_PWD_FILE = Path.home() / ".colorlab_pro" / ".pwd"

# Default password (SHA-256 of "colorlab").
_DEFAULT_HASH = hashlib.sha256(b"colorlab").hexdigest()


def _load_hash() -> str:
    """Return the stored password hash, or the default if not yet set."""
    if _PWD_FILE.exists():
        try:
            return _PWD_FILE.read_text(encoding="utf-8").strip()
        except Exception:  # noqa: BLE001
            pass
    return _DEFAULT_HASH


def _save_hash(h: str) -> None:
    """Persist the password hash to disk."""
    _PWD_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PWD_FILE.write_text(h, encoding="utf-8")


def _hash_password(plain: str) -> str:
    """Return the SHA-256 hex digest of *plain*."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def set_password(plain: str) -> None:
    """Public helper: change the stored password."""
    _save_hash(_hash_password(plain))


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class PasswordDialog(QDialog):
    """Modal dialog that asks for a password before the app starts.

    On first run the user must **set** a password (confirmed twice).
    On subsequent runs the user must **enter** the stored password.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ColorLab Pro")
        self.setFixedSize(380, 220)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._stored_hash = _load_hash()
        self._first_run = not _PWD_FILE.exists()

        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(14)

        # Title
        title = QLabel("🔐  ColorLab Pro")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        if self._first_run:
            # --- Set password flow ---
            self._pwd1 = self._add_field(root, "设置密码")
            self._pwd2 = self._add_field(root, "确认密码")
            btn = QPushButton("确认设置")
            btn.setObjectName("primary")
            btn.clicked.connect(self._on_set_password)
            root.addWidget(btn)

            hint = QLabel("首次使用，请设置一个登录密码")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet("color: var(--text-faint, #a1a1a6); font-size: 12px;")
            root.addWidget(hint)
        else:
            # --- Verify password flow ---
            self._pwd1 = self._add_field(root, "输入密码")
            self._pwd2 = None
            btn = QPushButton("解锁")
            btn.setObjectName("primary")
            btn.clicked.connect(self._on_verify_password)
            root.addWidget(btn)

        # Cancel
        cancel = QPushButton("退出")
        cancel.setStyleSheet("QPushButton { background-color: transparent; border: none; color: #8e8e93; } QPushButton:hover { color: #f5f5f7; }")
        cancel.clicked.connect(self.reject)
        root.addWidget(cancel)

    @staticmethod
    def _add_field(layout: QVBoxLayout, label_text: str) -> QLineEdit:
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 13px;")
        layout.addWidget(lbl)

        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText("••••••••")
        field.setMinimumHeight(36)
        layout.addWidget(field)
        field.returnPressed.connect(
            lambda _checked=False, f=field: f.parent().findChild(QPushButton).click()
            if isinstance(f.parent().findChild(QPushButton), QPushButton)
            else None
        )
        return field

    # ------------------------------------------------------------------ #
    # Handlers
    # ------------------------------------------------------------------ #

    def _on_set_password(self) -> None:
        p1 = self._pwd1.text()
        p2 = self._pwd2.text() if self._pwd2 else ""

        if not p1:
            QMessageBox.warning(self, "提示", "密码不能为空")
            return

        if len(p1) < 4:
            QMessageBox.warning(self, "提示", "密码长度不能少于 4 位")
            return

        if p1 != p2:
            QMessageBox.warning(self, "提示", "两次输入的密码不一致")
            self._pwd2.setFocus()
            self._pwd2.selectAll()
            return

        _save_hash(_hash_password(p1))
        self.accept()

    def _on_verify_password(self) -> None:
        p1 = self._pwd1.text()
        if not p1:
            QMessageBox.warning(self, "提示", "请输入密码")
            return

        if _hash_password(p1) != self._stored_hash:
            QMessageBox.warning(self, "提示", "密码错误")
            self._pwd1.setFocus()
            self._pwd1.selectAll()
            return

        self.accept()

    # ------------------------------------------------------------------ #
    # Keyboard shortcuts
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            # Find the primary button and click it
            btn = self.findChild(QPushButton)
            if btn:
                btn.click()
            return
        super().keyPressEvent(event)
