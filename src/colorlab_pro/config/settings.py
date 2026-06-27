"""Application settings and configuration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import yaml

_CONFIG_DIR = Path.home() / ".colorlab_pro"
_CONFIG_FILE = _CONFIG_DIR / "config.yaml"


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""

    app_name: str = "ColorLab Pro"
    app_version: str = "1.1.0"
    org_name: str = "ColorLab"

    # Database
    db_filename: str = "colorlab.db"
    data_dir_name: str = "data"
    user_dir_name: str = "user"
    default_project_dir: str = "default"

    # UI
    default_window_width: int = 1440
    default_window_height: int = 900

    # Spectrum
    default_wavelength_start: float = 380.0
    default_wavelength_end: float = 780.0
    default_wavelength_step: float = 1.0

    # Theme (always dark)
    default_theme: str = "dark"

    # Observer / Illuminant / Step
    default_observer: str = "CIE 1931 2 Degree Standard Observer"
    default_illuminant: str = "D65"
    default_step: int = 1

    # Optional custom database path (overrides the default location).
    db_path: str | None = None

    @property
    def base_data_path(self) -> Path:
        """Return the base data directory path.

        When ``data_dir_name`` is a relative path (the default ``"data"``),
        it is resolved under the user's home directory
        (``~/.colorlab_pro/data``) so the database location is independent of
        the current working directory. This prevents data loss when the
        application is launched from a shortcut whose working directory is
        not the project root (e.g. packaged ``.exe`` builds).

        When ``data_dir_name`` is an absolute path (used by tests and the
        ``db_path`` override), it is returned as-is.
        """
        candidate = Path(self.data_dir_name)
        if candidate.is_absolute():
            return candidate
        return Path.home() / ".colorlab_pro" / candidate

    @property
    def default_db_path(self) -> Path:
        """Return the SQLite database path."""
        if self.db_path:
            return Path(self.db_path)
        return (
            self.base_data_path / self.user_dir_name / self.default_project_dir / self.db_filename
        )


def get_config() -> AppConfig:
    """Return the global application configuration.

    Loads user overrides from ~/.colorlab_pro/config.yaml if present.
    """
    defaults = AppConfig()
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return replace(
                defaults,
                default_wavelength_start=float(
                    data.get("wavelength_start", defaults.default_wavelength_start)
                ),
                default_wavelength_end=float(
                    data.get("wavelength_end", defaults.default_wavelength_end)
                ),
                db_path=data.get("db_path", defaults.db_path),
                default_observer=data.get("default_observer", defaults.default_observer),
                default_illuminant=data.get("default_illuminant", defaults.default_illuminant),
                default_step=int(data.get("default_step", defaults.default_step)),
                default_theme=data.get("default_theme", defaults.default_theme),
            )
        except Exception as exc:  # noqa: BLE001
            # Log the failure so the user can diagnose why their custom
            # settings were ignored, instead of silently falling back.
            try:
                from loguru import logger

                logger.warning(
                    "Failed to load config from {}: {}; falling back to defaults.",
                    _CONFIG_FILE,
                    exc,
                )
            except Exception:  # noqa: BLE001
                pass
            return defaults
    return defaults


def save_config(
    *,
    wavelength_start: float | None = None,
    wavelength_end: float | None = None,
    db_path: str | None = None,
    default_observer: str | None = None,
    default_illuminant: str | None = None,
    default_step: int | None = None,
    default_theme: str | None = None,
) -> None:
    """Save user settings to ~/.colorlab_pro/config.yaml.

    Only the provided fields are updated; others are preserved.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing
    existing: dict = {}
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception:
            existing = {}

    # Update
    if wavelength_start is not None:
        existing["wavelength_start"] = wavelength_start
    if wavelength_end is not None:
        existing["wavelength_end"] = wavelength_end
    if db_path is not None:
        existing["db_path"] = db_path
    if default_observer is not None:
        existing["default_observer"] = default_observer
    if default_illuminant is not None:
        existing["default_illuminant"] = default_illuminant
    if default_step is not None:
        existing["default_step"] = default_step
    if default_theme is not None:
        existing["default_theme"] = default_theme

    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(existing, f, default_flow_style=False)
