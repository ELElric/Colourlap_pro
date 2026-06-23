"""Additional unit tests for AppConfig and settings I/O."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from colorlab_pro.config import settings
from colorlab_pro.config.settings import AppConfig, get_config, save_config


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect config directory to a temporary location."""
    config_dir = tmp_path / ".colorlab_pro"
    config_file = config_dir / "config.yaml"
    monkeypatch.setattr(settings, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(settings, "_CONFIG_FILE", config_file)
    return config_dir, config_file


def test_app_config_defaults():
    config = AppConfig()
    assert config.app_name == "ColorLab Pro"
    assert config.app_version == "1.1.0"
    assert config.org_name == "ColorLab"
    assert config.db_filename == "colorlab.db"
    assert config.default_window_width == 1440
    assert config.default_window_height == 900
    assert config.sidebar_width == 200
    assert config.default_wavelength_start == 380.0
    assert config.default_wavelength_end == 780.0
    assert config.default_wavelength_step == 1.0
    assert config.default_theme == "dark"
    assert config.default_observer == "CIE 1931 2 Degree Standard Observer"
    assert config.default_illuminant == "D65"
    assert config.default_step == 1
    assert config.db_path is None


def test_app_config_base_data_path():
    config = AppConfig(data_dir_name="custom_data")
    # Relative data_dir_name resolves under ~/.colorlab_pro/ so the database
    # location is independent of the current working directory.
    assert config.base_data_path == Path.home() / ".colorlab_pro" / "custom_data"


def test_app_config_base_data_path_absolute(tmp_path):
    # Absolute data_dir_name is returned as-is (used by tests / overrides).
    abs_data = tmp_path / "abs_data"
    config = AppConfig(data_dir_name=str(abs_data))
    assert config.base_data_path == abs_data


def test_app_config_default_db_path_without_override():
    config = AppConfig()
    assert config.default_db_path == config.base_data_path / "user" / "default" / "colorlab.db"


def test_app_config_default_db_path_with_override():
    config = AppConfig(db_path="/tmp/custom.db")
    assert config.default_db_path == Path("/tmp/custom.db")


def test_get_config_no_file(isolated_config):
    _, config_file = isolated_config
    assert not config_file.exists()
    config = get_config()
    assert config.default_theme == "dark"
    assert config.default_db_path == config.base_data_path / "user" / "default" / "colorlab.db"


def test_get_config_with_file(isolated_config):
    _, config_file = isolated_config
    config_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "theme": "light",
        "wavelength_start": 400,
        "wavelength_end": 700,
        "db_path": "/custom/path.db",
        "default_observer": "CIE 1964 10 Degree Standard Observer",
        "default_illuminant": "D50",
        "default_step": 5,
    }
    config_file.write_text(yaml.dump(data), encoding="utf-8")

    config = get_config()
    assert config.default_theme == "light"
    assert config.default_wavelength_start == 400.0
    assert config.default_wavelength_end == 700.0
    assert config.db_path == "/custom/path.db"
    assert config.default_observer == "CIE 1964 10 Degree Standard Observer"
    assert config.default_illuminant == "D50"
    assert config.default_step == 5


def test_get_config_bad_yaml_returns_defaults(isolated_config):
    _, config_file = isolated_config
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{invalid yaml", encoding="utf-8")

    config = get_config()
    assert config.default_theme == "dark"


def test_get_config_partial_yaml(isolated_config):
    _, config_file = isolated_config
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(yaml.dump({"theme": "light"}), encoding="utf-8")

    config = get_config()
    assert config.default_theme == "light"
    assert config.default_wavelength_start == 380.0


def test_save_config_creates_file(isolated_config):
    _, config_file = isolated_config
    assert not config_file.exists()
    save_config(theme="light", wavelength_start=400.0, wavelength_end=700.0)
    assert config_file.exists()
    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert data["theme"] == "light"
    assert data["wavelength_start"] == 400.0
    assert data["wavelength_end"] == 700.0


def test_save_config_preserves_existing(isolated_config):
    _, config_file = isolated_config
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(yaml.dump({"existing_key": "preserve"}), encoding="utf-8")

    save_config(theme="light")
    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert data["existing_key"] == "preserve"
    assert data["theme"] == "light"


def test_save_config_all_fields(isolated_config):
    _, config_file = isolated_config
    save_config(
        theme="dark",
        wavelength_start=390.0,
        wavelength_end=790.0,
        db_path="/db.sqlite",
        default_observer="CIE 1931 2 Degree Standard Observer",
        default_illuminant="D65",
        default_step=2,
    )
    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["wavelength_start"] == 390.0
    assert data["wavelength_end"] == 790.0
    assert data["db_path"] == "/db.sqlite"
    assert data["default_observer"] == "CIE 1931 2 Degree Standard Observer"
    assert data["default_illuminant"] == "D65"
    assert data["default_step"] == 2


def test_save_config_bad_existing_yaml(isolated_config):
    _, config_file = isolated_config
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{invalid yaml", encoding="utf-8")

    save_config(theme="light")
    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert data["theme"] == "light"
