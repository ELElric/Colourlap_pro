"""Worker classes for non-blocking background computation.

Uses PySide6's QThreadPool with QRunnable for thread-safe
background tasks that emit results back to the UI thread.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    """Signals that a Worker can emit.

    Must be a QObject subclass to define signals.
    """

    finished = Signal()
    """Emitted when the worker completes, regardless of success."""

    result = Signal(object)
    """Emitted with the return value of the worker function."""

    error = Signal(str)
    """Emitted with the error message if the worker raises."""

    def __init__(self) -> None:
        super().__init__()


class Worker(QRunnable):
    """A QRunnable that executes a callable in a background thread.

    Results and errors are emitted via signals that can be connected
    to UI slots safely (cross-thread signal emission is handled by Qt).

    Example:
        worker = Worker(lambda: expensive_function(data))
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, fn: Callable[[], Any]) -> None:
        """Initialize with a no-argument callable.

        Args:
            fn: The function to run in the background thread.
        """
        super().__init__()
        self._fn = fn
        self.signals = WorkerSignals()

    def run(self) -> None:
        """Execute the worker function and emit signals."""
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


def run_in_background(
    fn: Callable[[], Any],
    *,
    on_result: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    on_finished: Callable[[], None] | None = None,
) -> Worker:
    """Convenience helper to run a function in the global QThreadPool.

    Args:
        fn: The function to run in the background.
        on_result: Optional callback for successful results.
        on_error: Optional callback for error messages.
        on_finished: Optional callback called on completion.

    Returns:
        The Worker instance (already started in the pool).
    """
    from PySide6.QtCore import QThreadPool

    worker = Worker(fn)
    if on_result is not None:
        worker.signals.result.connect(on_result)
    if on_error is not None:
        worker.signals.error.connect(on_error)
    if on_finished is not None:
        worker.signals.finished.connect(on_finished)
    QThreadPool.globalInstance().start(worker)
    return worker
