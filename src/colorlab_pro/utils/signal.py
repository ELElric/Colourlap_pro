"""Lightweight signal/slot replacement for PySide6 QObject and Signal.

Provides a pure-Python event mechanism so controllers can emit signals
without depending on PySide6.  The API mirrors PySide6's Signal/QObject
closely enough for drop-in replacement.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Signal:
    """Minimal Signal implementation supporting connect/emit."""

    def __init__(self, *types: type) -> None:
        self._callbacks: list[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., Any] | None = None) -> None:
        if callback is None:
            self._callbacks.clear()
        elif callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self, *args: Any) -> None:
        for cb in self._callbacks:
            cb(*args)


class QObject:
    """Minimal QObject replacement — no event loop required."""

    def __init__(self, parent: "QObject | None" = None) -> None:
        self._parent = parent
