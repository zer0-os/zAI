"""Custom exceptions for database operations."""


class DatabaseConnectionError(Exception):
    """Raised when database connection cannot be established."""

    pass


class DatabaseConfigError(Exception):
    """Raised when database configuration is invalid or missing."""

    pass
