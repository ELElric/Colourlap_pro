"""pywebview 版本的 ColorLab Pro 入口文件.

使用 pywebview + 内置 HTTP server 提供前端页面。
"""

from __future__ import annotations

import socket
import sys
import threading
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import webview  # type: ignore[import-untyped]

from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.ui.pywebview_api import ColorLabApi
from colorlab_pro.utils.default_data_loader import load_default_spectra
from colorlab_pro.utils.paths import ensure_data_directory, get_default_db_path


# ------------------------------------------------------------------ #
# Logging setup
# ------------------------------------------------------------------ #


def _setup_logging() -> None:
    """Enable loguru logging as early as possible."""
    try:
        from colorlab_pro.utils.logging import setup_logging as _setup

        _setup()
    except Exception:  # noqa: BLE001
        pass


def _install_excepthook() -> None:
    """Install a global excepthook that logs uncaught exceptions."""

    def hook(exc_type, exc_value, exc_tb):  # type: ignore[no-untyped-def]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        try:
            from loguru import logger

            logger.exception("Uncaught exception: {}: {}", exc_type.__name__, exc_value)
        except Exception:  # noqa: BLE001
            pass
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


# ------------------------------------------------------------------ #
# Database initialization
# ------------------------------------------------------------------ #


def _ensure_project_with_spectra(
    main_ctrl: MainController, project_ctrl: ProjectController
) -> None:
    """Ensure the current project has spectra, else switch to one that does.

    Since pywebview has no QSettings, this uses a simpler heuristic:
    switch to the project with the most spectra when the current project
    is empty.
    """
    current_id = main_ctrl.current_project_id
    if current_id is None:
        return

    try:
        projects = project_ctrl.list_projects()
    except Exception:  # noqa: BLE001
        return

    if not projects:
        return

    best_project_id = current_id
    max_spectra = 0

    for project in projects:
        pid = project.id
        count = project.spectrum_count

        if pid == current_id:
            if count > 0:
                return
            max_spectra = count
        elif count > max_spectra:
            max_spectra = count
            best_project_id = pid

    if best_project_id != current_id and max_spectra > 0:
        main_ctrl.set_current_project(best_project_id)


# ------------------------------------------------------------------ #
# HTTP Server
# ------------------------------------------------------------------ #


def _find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _create_http_server(directory: Path, port: int) -> HTTPServer:
    """Create an HTTP server serving files from *directory* on *port*."""

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format, *args):  # type: ignore[no-untyped-def, override]
            # Suppress per-request logging to keep console clean
            pass

    server = HTTPServer(("127.0.0.1", port), _Handler)
    return server


# ------------------------------------------------------------------ #
# Main entry point
# ------------------------------------------------------------------ #


def main(argv: list[str] | None = None) -> int:
    """Launch ColorLab Pro with pywebview.

    1. Initialize database and controllers
    2. Start a local HTTP server to serve HTML/JS/CSS assets
    3. Create a pywebview window pointing to that server
    4. Expose the unified API class for JS<->Python communication

    Returns:
        Exit code (0 on success, non-zero on error).
    """
    _setup_logging()
    _install_excepthook()

    # --- Initialize database and controllers --------------------------
    main_ctrl = MainController()
    try:
        main_ctrl.initialize()
    except Exception as exc:
        print(f"Failed to initialize database: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    # Ensure a default project exists
    project_ctrl = ProjectController(main_ctrl)
    if main_ctrl.current_project_id is None:
        pid = project_ctrl.create_project("Default Project")
        if pid is not None:
            main_ctrl.set_current_project(pid)

    # Load bundled test spectra
    load_default_spectra(main_ctrl)

    # Ensure current project has spectra
    _ensure_project_with_spectra(main_ctrl, project_ctrl)

    # --- Prepare web assets directory ----------------------------------
    web_dir = Path(__file__).resolve().parent / "web"
    if not web_dir.is_dir():
        print(f"Web assets directory not found: {web_dir}", file=sys.stderr)
        main_ctrl.shutdown()
        return 1

    # --- Start HTTP server in background thread -----------------------
    port = _find_free_port()
    server = _create_http_server(web_dir, port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # --- Create API and pywebview window -------------------------------
    api = ColorLabApi(main_ctrl)
    # Ensure background optimization threads are stopped before the
    # database engine is disposed during shutdown.
    main_ctrl.register_shutdown_callback(api.optimizer_stop_and_wait)
    url = f"http://127.0.0.1:{port}/index.html"

    # Apply saved window geometry
    saved_state = api.get_window_state()
    win_width = saved_state.get("width", 1600)
    win_height = saved_state.get("height", 900)
    win_x = saved_state.get("x")
    win_y = saved_state.get("y")

    try:
        window_kwargs: dict = {
            "js_api": api,
            "width": win_width,
            "height": win_height,
            "min_size": (1200, 700),
        }
        if win_x is not None and win_y is not None:
            window_kwargs["x"] = win_x
            window_kwargs["y"] = win_y
        window = webview.create_window("ColorLab Pro", url, **window_kwargs)

        # Wire window reference into API for JS evaluation (progress push)
        api.set_window(window)

        # Save window state on close
        def _on_closing():
            try:
                import webview as _wv

                for w in _wv.windows:
                    api.save_window_state({
                        "width": w.width,
                        "height": w.height,
                        "x": w.x,
                        "y": w.y,
                    })
                    break
            except Exception:  # noqa: BLE001
                pass

        window.events.closing += _on_closing

        webview.start(debug="--debug" in (argv or []))
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        server.shutdown()
        main_ctrl.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
