"""ContextMenuMixin — adds right-click context menus to Qt widgets.

Provides a reusable mixin for attaching context menus to any QWidget.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMenu


class ContextMenuMixin:
    """Mixin that adds a right-click context menu to a QWidget.

    Subclasses must call _init_context_menu() in their __init__
    and can register actions via add_context_action().

    Example:
        class MyWidget(QWidget, ContextMenuMixin):
            def __init__(self):
                super().__init__()
                self._init_context_menu()
                self.add_context_action("Delete", self._on_delete)
    """

    def _init_context_menu(self) -> None:
        """Initialize the context menu system."""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._context_actions: list[tuple[str, Callable[[], None]]] = []

    def add_context_action(self, label: str, callback: Callable[[], None]) -> None:
        """Register a context menu action.

        Args:
            label: Display text for the menu item.
            callback: Function to call when the item is selected.
        """
        self._context_actions.append((label, callback))

    def _show_context_menu(self, pos: QPoint) -> None:
        """Build and show the context menu at the given position."""
        if not self._context_actions:
            return
        menu = QMenu(self)
        for label, callback in self._context_actions:
            action = menu.addAction(label)
            action.triggered.connect(callback)
        menu.exec(self.mapToGlobal(pos))
