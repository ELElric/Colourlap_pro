"""Unit tests for AppConfig."""

from __future__ import annotations

from colorlab_pro.config.settings import AppConfig, get_config


def test_default_config():
    config = get_config()
    assert config.app_name == "ColorLab Pro"
    assert config.app_version == "1.1.0"
    assert config.default_theme == "dark"
    assert config.default_window_width == 1440


def test_db_path():
    config = AppConfig()
    assert config.default_db_path == config.base_data_path / "user" / "default" / "colorlab.db"
