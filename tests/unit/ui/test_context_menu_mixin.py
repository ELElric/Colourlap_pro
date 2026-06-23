"""Tests for ContextMenuMixin."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from colorlab_pro.ui.widgets.context_menu_mixin import ContextMenuMixin


class TestWidget(QWidget, ContextMenuMixin):
    def __init__(self) -> None:
        super().__init__()
        self._init_context_menu()
        self.deleted = False
        self.add_context_action("Delete", self._on_delete)

    def _on_delete(self) -> None:
        self.deleted = True


class TestContextMenuMixin:
    def test_creation(self, qtbot) -> None:
        widget = TestWidget()
        qtbot.addWidget(widget)
        assert len(widget._context_actions) == 1

    def test_menu_policy(self, qtbot) -> None:
        widget = TestWidget()
        qtbot.addWidget(widget)
        assert widget.contextMenuPolicy().name == "CustomContextMenu"
