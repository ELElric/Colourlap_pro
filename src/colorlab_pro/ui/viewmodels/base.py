"""ViewModel base class for MVVM pattern."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class ViewModel(QObject):
    """Base ViewModel with common error/success signals.

    All page-specific viewmodels should inherit from this class.
    """

    error_occurred = Signal(str)
    """Emitted when an error message should be shown to the user."""

    status_changed = Signal(str)
    """Emitted when the status bar text should be updated."""

    data_changed = Signal()
    """Emitted when the underlying data has changed and UI should refresh."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def set_error(self, message: str) -> None:
        """Emit an error signal."""
        self.error_occurred.emit(message)

    def set_status(self, message: str) -> None:
        """Emit a status update signal."""
        self.status_changed.emit(message)
