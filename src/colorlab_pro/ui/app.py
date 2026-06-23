"""Main application entry point for ColorLab Pro GUI."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from colorlab_pro.config.settings import get_config
from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.ui.main_window import create_application
from colorlab_pro.ui.pages.gamut_calculator_page import GamutCalculatorPage
from colorlab_pro.ui.pages.spectrum_page import SpectrumPage
from colorlab_pro.ui.pages.thickness_optimizer_page import ThicknessOptimizerPage
from colorlab_pro.ui.pages.white_point_page import WhitePointPage


def _install_excepthook() -> None:
    """Install a global excepthook that logs uncaught exceptions.

    In GUI mode uncaught exceptions would otherwise silently abort the event
    loop. We log them and print the traceback so packaged (windowed) builds
    still leave a diagnostic trail.
    """

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


def _show_fatal_error(exc: Exception) -> None:
    """Best-effort fatal-error dialog so the user is not left with a bare crash."""
    log_dir: str = "~/.colorlab_pro/logs"
    try:
        from colorlab_pro.utils.logging import get_log_dir

        log_dir = str(get_log_dir())
    except Exception:  # noqa: BLE001
        pass

    message = (
        f"ColorLab Pro encountered a fatal error and cannot continue.\n\n"
        f"Error: {exc}\n\n"
        f"Please see the log file under:\n{log_dir}\n\n"
        f"Contact support with the log file for assistance."
    )
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        QMessageBox.critical(None, "ColorLab Pro — Fatal Error", message)
    except Exception:  # noqa: BLE001
        # If Qt is unavailable, fall back to stderr.
        print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Launch the ColorLab Pro main window.

    Initializes the database, creates all controllers and pages,
    and registers them with the MainWindow.

    Args:
        argv: Command-line arguments. Uses sys.argv if None.

    Returns:
        Application exit code.
    """
    # Enable logging as early as possible so that startup failures are
    # captured to ~/.colorlab_pro/logs/colorlab_pro.log.
    log_dir: Path | None = None
    try:
        from colorlab_pro.utils.logging import setup_logging

        log_dir = setup_logging()
    except Exception:  # noqa: BLE001
        pass

    _install_excepthook()

    try:
        return _run(argv, log_dir)
    except Exception as exc:  # noqa: BLE001
        try:
            from loguru import logger

            logger.exception("Fatal error during startup: {}", exc)
        except Exception:  # noqa: BLE001
            pass
        _show_fatal_error(exc)
        return 1


def _run(argv: list[str] | None, log_dir: Path | None) -> int:  # noqa: ARG001
    """Inner runner wrapped by :func:`main` for exception safety."""
    app = create_application(argv if argv is not None else sys.argv)

    # Load theme stylesheet at startup
    theme = get_config().default_theme
    qss_path = Path(__file__).resolve().parent / "resources" / "styles" / f"{theme}.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    # Initialize the application controller (database + services)
    main_ctrl = MainController()
    main_ctrl.initialize()

    # Ensure a default project exists (empty, for immediate use)
    if main_ctrl.current_project_id is None:
        project_ctrl = ProjectController(main_ctrl)
        pid = project_ctrl.create_project("Default Project")
        if pid is not None:
            main_ctrl.set_current_project(pid)

    # Create the main window
    window = main_ctrl.create_window()

    # Create sub-controllers
    spec_ctrl = SpectrumController(main_ctrl)
    color_ctrl = ColorController(main_ctrl)
    opt_ctrl = OptimizationController(main_ctrl)

    # Create and register workspace pages
    # 0: Spectrum Library
    spectrum_page = SpectrumPage(spec_ctrl, page_index=0)
    # 1: Gamut Calculator
    gamut_page = GamutCalculatorPage(spec_ctrl, color_ctrl, page_index=1)
    # 2: White Point
    white_point_page = WhitePointPage(color_ctrl, page_index=2)
    # 3: Thickness Optimizer
    optimizer_page = ThicknessOptimizerPage(spec_ctrl, color_ctrl, opt_ctrl, page_index=3)

    pages = [
        ("Spectrum Library", spectrum_page),
        ("Gamut Calculator", gamut_page),
        ("White Point", white_point_page),
        ("Thickness Optimizer", optimizer_page),
    ]
    for name, page in pages:
        window.add_page(page, name)

    # Wire sidebar navigation — MainWindow._on_nav_changed handles the mapping
    # Do NOT connect to main_ctrl.switch_to_page as it bypasses the nav_map logic.

    # Auto-refresh: pages reload data when switched to
    for _name, page in pages:
        if hasattr(page, "connect_auto_refresh"):
            page.connect_auto_refresh(window)

    # Cross-page wiring: Gamut Calculator RGB coordinates -> White Point
    gamut_page.white_point_calculated.connect(white_point_page.set_rgb_coordinates)

    # Connect status messages to status bar
    main_ctrl.status_message.connect(window.statusBar().showMessage)

    window.show()
    exit_code = int(app.exec())

    main_ctrl.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
