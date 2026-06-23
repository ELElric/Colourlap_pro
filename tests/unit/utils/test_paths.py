"""Unit tests for path utilities."""

from __future__ import annotations

from colorlab_pro.utils.paths import ensure_data_directory, get_default_db_path


def test_ensure_data_directory(tmp_path, monkeypatch):
    from colorlab_pro.config import settings

    monkeypatch.setattr(
        settings, "get_config", lambda: settings.AppConfig(data_dir_name=str(tmp_path / "data"))
    )
    path = ensure_data_directory()
    assert path.exists()


def test_get_default_db_path(tmp_path, monkeypatch):
    from colorlab_pro.config import settings

    monkeypatch.setattr(
        settings, "get_config", lambda: settings.AppConfig(data_dir_name=str(tmp_path / "data"))
    )
    path = get_default_db_path()
    assert path.parent.exists()
    assert path.name == "colorlab.db"
