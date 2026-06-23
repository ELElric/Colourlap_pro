"""Path utilities for the application."""

from __future__ import annotations

from pathlib import Path

from colorlab_pro.config.settings import get_config


def ensure_data_directory() -> Path:
    """Create the default data directory tree if it does not exist.

    Returns:
        Path to the default database directory.
    """
    config = get_config()
    db_dir = config.default_db_path.parent
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def get_default_db_path() -> Path:
    """Return the default SQLite database file path.

    Ensures the parent directory exists.
    """
    ensure_data_directory()
    return get_config().default_db_path
