"""ColorLab Pro command-line interface."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from colorlab_pro import __version__
from colorlab_pro.database.session import create_engine_from_path, init_schema


def _cmd_init_db(args: argparse.Namespace) -> int:
    engine = create_engine_from_path(args.db_path)
    init_schema(engine)
    print(f"Initialized database: {args.db_path}")
    return 0


def _cmd_gui(_args: argparse.Namespace) -> int:
    from colorlab_pro.ui.app import main as gui_main

    return gui_main()


def _cmd_version(_args: argparse.Namespace) -> int:
    print(__version__)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(prog="colorlab-pro", description="ColorLab Pro CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Initialize the SQLite database")
    init_parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data") / "user" / "default" / "colorlab.db",
    )
    init_parser.set_defaults(func=_cmd_init_db)

    gui_parser = subparsers.add_parser("gui", help="Launch the graphical user interface")
    gui_parser.set_defaults(func=_cmd_gui)

    version_parser = subparsers.add_parser("version", help="Print the version")
    version_parser.set_defaults(func=_cmd_version)

    return parser


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


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ColorLab Pro CLI."""
    # Enable logging as early as possible so that failures during command
    # execution are captured to ~/.colorlab_pro/logs/colorlab_pro.log.
    try:
        from colorlab_pro.utils.logging import setup_logging

        setup_logging()
    except Exception:  # noqa: BLE001
        pass

    _install_excepthook()

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001
        try:
            from loguru import logger

            logger.exception("CLI command failed: {}", exc)
        except Exception:  # noqa: BLE001
            pass
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
