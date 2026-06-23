"""Unit tests for custom exceptions."""

from __future__ import annotations

import pytest

from colorlab_pro.utils.errors import (
    ColorLabError,
    ComputationError,
    SpectrumImportError,
    ValidationError,
)


def test_colorlab_error_attributes():
    error = ColorLabError("E001", "Something went wrong", field="value")
    assert error.code == "E001"
    assert error.message == "Something went wrong"
    assert error.details == {"field": "value"}
    assert str(error) == "Something went wrong"


def test_colorlab_error_without_details():
    error = ColorLabError("E002", "No details")
    assert error.details == {}


@pytest.mark.parametrize("exc_class", [ValidationError, SpectrumImportError, ComputationError])
def test_error_subclasses(exc_class):
    error = exc_class("E003", "Subclass error", key="test")
    assert isinstance(error, ColorLabError)
    assert error.code == "E003"
    assert error.message == "Subclass error"
    assert error.details == {"key": "test"}


def test_validation_error_catchable():
    with pytest.raises(ValidationError):
        raise ValidationError("V001", "Invalid input")


def test_spectrum_import_error_catchable():
    with pytest.raises(SpectrumImportError):
        raise SpectrumImportError("I001", "Parse failed")


def test_computation_error_catchable():
    with pytest.raises(ComputationError):
        raise ComputationError("C001", "Did not converge")
