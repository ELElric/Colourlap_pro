"""Unit tests for the ColorLab Pro CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from colorlab_pro import __version__
from colorlab_pro.cli import _cmd_gui, _cmd_init_db, _cmd_version, build_parser, main


def test_build_parser_returns_parser():
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    assert parser.prog == "colorlab-pro"


def test_main_version(capsys):
    assert main(["version"]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__


def test_cmd_version(capsys):
    args = argparse.Namespace()
    assert _cmd_version(args) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__


def test_cmd_init_db(tmp_path, capsys):
    db_path = tmp_path / "test.db"
    args = argparse.Namespace(db_path=db_path)

    mock_engine = MagicMock()
    with patch("colorlab_pro.cli.create_engine_from_path", return_value=mock_engine) as mock_create:
        with patch("colorlab_pro.cli.init_schema") as mock_init:
            assert _cmd_init_db(args) == 0

    mock_create.assert_called_once_with(db_path)
    mock_init.assert_called_once_with(mock_engine)
    captured = capsys.readouterr()
    assert f"Initialized database: {db_path}" in captured.out


def test_main_init_db(tmp_path, capsys):
    db_path = tmp_path / "test.db"
    mock_engine = MagicMock()
    with patch("colorlab_pro.cli.create_engine_from_path", return_value=mock_engine):
        with patch("colorlab_pro.cli.init_schema"):
            assert main(["init-db", "--db-path", str(db_path)]) == 0
    captured = capsys.readouterr()
    assert "Initialized database" in captured.out


def test_cmd_gui():
    args = argparse.Namespace()
    with patch("colorlab_pro.ui.app.main", return_value=0) as mock_gui:
        assert _cmd_gui(args) == 0
    mock_gui.assert_called_once()


def test_main_gui():
    with patch("colorlab_pro.ui.app.main", return_value=0) as mock_gui:
        assert main(["gui"]) == 0
    mock_gui.assert_called_once()


def test_main_no_command_exits():
    with pytest.raises(SystemExit):
        main([])


def test_default_db_path_in_parser():
    parser = build_parser()
    init_parser = parser._subparsers._group_actions[0].choices["init-db"]
    default = init_parser.get_default("db_path")
    assert default == Path("data") / "user" / "default" / "colorlab.db"
