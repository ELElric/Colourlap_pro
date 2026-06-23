"""Tests for utils.default_data_loader module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from colorlab_pro.utils.default_data_loader import (
    DEFAULT_PROJECT_DESCRIPTION,
    DEFAULT_PROJECT_NAME,
    DEFAULT_SPECTRA,
    _all_spectrum_ids,
    _existing_spectrum_names,
    _find_test_data_dir,
    _get_or_create_default_project,
    load_default_spectra,
)


def test_default_spectra_format():
    """Test that DEFAULT_SPECTRA has correct format."""
    assert isinstance(DEFAULT_SPECTRA, tuple)
    assert len(DEFAULT_SPECTRA) > 0
    for item in DEFAULT_SPECTRA:
        assert isinstance(item, tuple)
        assert len(item) == 3
        assert isinstance(item[0], str)
        assert isinstance(item[1], str)
        assert isinstance(item[2], str)


def test_default_project_constants():
    """Test that project constants are defined."""
    assert isinstance(DEFAULT_PROJECT_NAME, str)
    assert isinstance(DEFAULT_PROJECT_DESCRIPTION, str)
    assert len(DEFAULT_PROJECT_NAME) > 0


class TestFindTestDataDir:
    def test_returns_path_or_none(self) -> None:
        """_find_test_data_dir returns Path or None depending on filesystem."""
        result = _find_test_data_dir()
        assert result is None or isinstance(result, Path)


class TestGetOrCreateDefaultProject:
    def test_returns_none_when_no_session_factory(self) -> None:
        main_ctrl = MagicMock()
        main_ctrl._session_factory = None
        project_ctrl = MagicMock()
        result = _get_or_create_default_project(main_ctrl, project_ctrl)
        assert result is None

    def test_returns_existing_project_id(self) -> None:
        main_ctrl = MagicMock()
        project_ctrl = MagicMock()
        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.id = 42
        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        main_ctrl._session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        main_ctrl._session_factory.return_value.__exit__ = MagicMock(return_value=False)
        result = _get_or_create_default_project(main_ctrl, project_ctrl)
        assert result == 42

    def test_creates_new_project_when_not_exists(self) -> None:
        main_ctrl = MagicMock()
        project_ctrl = MagicMock()
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        main_ctrl._session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        main_ctrl._session_factory.return_value.__exit__ = MagicMock(return_value=False)
        project_ctrl.create_project.return_value = 99
        result = _get_or_create_default_project(main_ctrl, project_ctrl)
        assert result == 99
        project_ctrl.create_project.assert_called_once_with(
            DEFAULT_PROJECT_NAME, description=DEFAULT_PROJECT_DESCRIPTION
        )

    def test_returns_none_when_create_fails(self) -> None:
        main_ctrl = MagicMock()
        project_ctrl = MagicMock()
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        main_ctrl._session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        main_ctrl._session_factory.return_value.__exit__ = MagicMock(return_value=False)
        project_ctrl.create_project.return_value = None
        result = _get_or_create_default_project(main_ctrl, project_ctrl)
        assert result is None


class TestExistingSpectrumNames:
    def test_returns_lower_cased_names(self) -> None:
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [
            ("LED_R",),
            ("CF_Blue",),
        ]
        factory = MagicMock()
        factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        factory.return_value.__exit__ = MagicMock(return_value=False)
        result = _existing_spectrum_names(factory, project_id=1)
        assert result == {"led_r", "cf_blue"}

    def test_handles_empty_names(self) -> None:
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [(None,), ("",)]
        factory = MagicMock()
        factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        factory.return_value.__exit__ = MagicMock(return_value=False)
        result = _existing_spectrum_names(factory, project_id=1)
        assert result == set()


class TestAllSpectrumIds:
    def test_returns_sorted_ids(self) -> None:
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            (3,),
            (1,),
            (2,),
        ]
        factory = MagicMock()
        factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        factory.return_value.__exit__ = MagicMock(return_value=False)
        result = _all_spectrum_ids(factory, project_id=1)
        assert result == [3, 1, 2]


class TestLoadDefaultSpectra:
    def test_returns_empty_when_no_project(self) -> None:
        main_ctrl = MagicMock()
        main_ctrl._session_factory = None
        result = load_default_spectra(main_ctrl)
        assert result == []

    def test_returns_empty_when_no_session_factory(self) -> None:
        main_ctrl = MagicMock()
        main_ctrl._session_factory = None
        result = load_default_spectra(main_ctrl)
        assert result == []

    def test_returns_ids_when_no_test_data(self) -> None:
        main_ctrl = MagicMock()
        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            (10,),
            (20,),
        ]
        main_ctrl._session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        main_ctrl._session_factory.return_value.__exit__ = MagicMock(return_value=False)
        with patch("colorlab_pro.utils.default_data_loader._find_test_data_dir", return_value=None):
            result = load_default_spectra(main_ctrl)
        assert result == [10, 20]
