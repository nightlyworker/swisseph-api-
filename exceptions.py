"""Custom exceptions for Swiss Ephemeris API."""


class SwissEphAPIException(Exception):
    """Base exception for all API errors."""
    pass


class ChartCalculationError(SwissEphAPIException):
    """Raised when chart calculation fails."""
    pass


class InvalidDateTimeError(SwissEphAPIException):
    """Raised when datetime is invalid."""
    pass


class InvalidCoordinatesError(SwissEphAPIException):
    """Raised when coordinates are invalid."""
    pass


class InvalidTimezoneError(SwissEphAPIException):
    """Raised when timezone is invalid."""
    pass
