"""Unit tests for logging setup."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from colorlab_pro.utils.logging import DEFAULT_LOG_DIR, setup_logging


def test_setup_logging_default_also_writes_file():
    """With no log_dir, file logging is still enabled (C-02 fix)."""
    with patch("colorlab_pro.utils.logging.sys.stderr") as mock_stderr:
        with patch("colorlab_pro.utils.logging.logger") as mock_logger:
            setup_logging()
    mock_logger.remove.assert_called_once()
    # Two sinks: stderr + file (always on so logs survive in packaged builds)
    assert mock_logger.add.call_count == 2
    stderr_call = mock_logger.add.call_args_list[0]
    file_call = mock_logger.add.call_args_list[1]
    assert stderr_call.args[0] is mock_stderr
    assert stderr_call.kwargs["level"] == "INFO"
    assert file_call.args[0] == DEFAULT_LOG_DIR / "colorlab_pro.log"
    assert file_call.kwargs["level"] == "INFO"
    assert file_call.kwargs["rotation"] == "10 MB"
    assert file_call.kwargs["retention"] == "30 days"


def test_setup_logging_with_log_dir(tmp_path):
    log_dir = tmp_path / "logs"
    with patch("colorlab_pro.utils.logging.logger") as mock_logger:
        setup_logging(log_dir=log_dir, level="DEBUG")
    assert log_dir.exists()
    mock_logger.remove.assert_called_once()
    assert mock_logger.add.call_count == 2
    stderr_call = mock_logger.add.call_args_list[0]
    file_call = mock_logger.add.call_args_list[1]
    assert stderr_call.kwargs["level"] == "DEBUG"
    assert file_call.args[0] == log_dir / "colorlab_pro.log"
    assert file_call.kwargs["rotation"] == "10 MB"
    assert file_call.kwargs["retention"] == "30 days"
    assert file_call.kwargs["level"] == "DEBUG"


def test_setup_logging_returns_log_dir(tmp_path):
    log_dir = tmp_path / "logs"
    returned = setup_logging(log_dir=log_dir)
    assert returned == log_dir
    assert isinstance(returned, Path)
