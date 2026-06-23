"""Custom exceptions."""


class ColorLabError(Exception):
    """Base class for all ColorLab Pro errors."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class ValidationError(ColorLabError):
    """Raised when input validation fails."""


class SpectrumImportError(ColorLabError):
    """Raised when a file cannot be parsed."""


class ComputationError(ColorLabError):
    """Raised when a numerical computation fails to converge."""
