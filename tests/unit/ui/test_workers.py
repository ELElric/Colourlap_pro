"""Tests for Worker and run_in_background."""

from __future__ import annotations

from colorlab_pro.ui.workers import Worker, run_in_background


class TestWorker:
    def test_worker_emits_result(self, qtbot) -> None:
        worker = Worker(lambda: 42)
        results = []
        worker.signals.result.connect(results.append)
        with qtbot.waitSignal(worker.signals.finished, timeout=2000):
            worker.run()
        assert results == [42]

    def test_worker_emits_error(self, qtbot) -> None:
        def fail():
            raise RuntimeError("boom")

        worker = Worker(fail)
        errors = []
        worker.signals.error.connect(errors.append)
        with qtbot.waitSignal(worker.signals.finished, timeout=2000):
            worker.run()
        assert len(errors) == 1
        assert "boom" in errors[0]


class TestRunInBackground:
    def test_run_in_background(self, qtbot) -> None:
        results = []
        worker = run_in_background(lambda: 99, on_result=results.append)
        with qtbot.waitSignal(worker.signals.finished, timeout=2000):
            pass
        assert results == [99]
