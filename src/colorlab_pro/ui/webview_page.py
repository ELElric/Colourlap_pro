"""Base class for workspace pages backed by QWebEngineView."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget


class WebViewPage(QWidget):
    """A workspace page that renders an HTML UI inside a QWebEngineView.

    Subclasses provide:
      - an HTML file via :meth:`html_path`
      - a backend QObject via :meth:`create_backend`
      - optional JavaScript setup via :meth:`page_script`

    The page uses :meth:`QWebEngineView.setHtml` instead of loading a local
    file so that the Qt WebChannel transport is available to the page JS.
    The page script is executed after a short delay so the transport is fully
    ready (calling it immediately after ``setHtml`` is too early).
    """

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backend: QObject | None = None
        self._initialized = False
        self._setup_done = False
        self._build_ui()
        self._channel = QWebChannel(self)
        self._view.page().setWebChannel(self._channel)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._view = QWebEngineView(self)
        layout.addWidget(self._view)

    def html_path(self) -> Path:
        """Return the path to the HTML file rendered by this page."""
        raise NotImplementedError

    def create_backend(self) -> QObject:
        """Create and return the backend QObject exposed to the page JS."""
        raise NotImplementedError

    def page_script(self) -> str:
        """Return extra JavaScript run after the HTML loads.

        The script can assume ``QWebChannel`` and ``qt.webChannelTransport``
        are available (qwebchannel.js is referenced by the HTML).
        """
        return ""

    def initialize(self) -> None:
        """Register the backend and load the page HTML."""
        if self._initialized:
            return
        self._initialized = True
        self._backend = self.create_backend()
        self._channel.registerObject("backend", self._backend)

        html = self.html_path()
        if not html.exists():
            self._view.setHtml(f"<html><body><h1>Missing page: {html.name}</h1></body></html>")
            self._finish_setup()
            return

        # setHtml makes the Qt WebChannel transport available; loading a
        # plain local file does not. Wait briefly so the transport is ready.
        self._view.setHtml(html.read_text(encoding="utf-8"))
        QTimer.singleShot(1200, self._finish_setup)

    def _finish_setup(self) -> None:
        """Run the page script and notify that the page is ready."""
        if self._setup_done:
            return
        self._setup_done = True
        script = self.page_script()
        if script:
            self._view.page().runJavaScript(script)
        self.status_message.emit("Ready")

    def run_javascript(self, script: str, callback: Any | None = None) -> None:
        """Execute JavaScript in the page context."""
        if callback is None:
            self._view.page().runJavaScript(script)
        else:
            self._view.page().runJavaScript(script, callback)

    def connect_auto_refresh(self, window: QWidget) -> None:
        """Hook the page into MainWindow's page_about_to_show signal."""
        window.page_about_to_show.connect(self._on_page_about_to_show)

    def _on_page_about_to_show(self, index: int) -> None:
        """Called when the stacked widget switches to this page.

        Subclasses may override this to refresh data by emitting signals or
        running JavaScript.
        """
        pass
