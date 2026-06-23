"""Logging setup using loguru."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

# Default log directory under the user's home directory so logs survive
# regardless of the current working directory (important for packaged builds).
DEFAULT_LOG_DIR: Path = Path.home() / ".colorlab_pro" / "logs"


def get_log_dir() -> Path:
    """Return the log directory used by :func:`setup_logging`.

    The directory is created on first call.
    """
    log_dir = DEFAULT_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(log_dir: Path | None = None, level: str = "INFO") -> Path:
    """Configure the global loguru logger.

    Args:
        log_dir: Optional override for the log directory. Defaults to
            ``~/.colorlab_pro/logs`` so logs are always writable in packaged
            builds regardless of the current working directory.
        level: Logging level string (e.g. ``"INFO"``, ``"DEBUG"``).

    Returns:
        The resolved log directory path (useful for showing to the user in
        error dialogs).
    """
    target_dir = log_dir if log_dir is not None else DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(sys.stderr, level=level)
    logger.add(
        target_dir / "colorlab_pro.log",
        rotation="10 MB",
        retention="30 days",
        level=level,
        encoding="utf-8",
    )
    return target_dir
