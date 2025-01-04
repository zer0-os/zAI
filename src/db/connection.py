"""Database connection management module."""

from typing import Optional, Generator
import os
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extensions import connection
from .exceptions import DatabaseConnectionError, DatabaseConfigError


class DatabaseConnection:
    """Manages database connections using a connection pool."""

    def __init__(self) -> None:
        """Initialize the database connection manager."""
        self._pool: Optional[SimpleConnectionPool] = None
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize the connection pool with environment variables."""
        try:
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                raise DatabaseConfigError(
                    "DATABASE_URL environment variable is not set"
                )

            self._pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=db_url)
        except psycopg2.Error as e:
            raise DatabaseConnectionError(
                f"Failed to initialize database pool: {str(e)}"
            )

    @contextmanager
    def get_connection(self) -> Generator[connection, None, None]:
        """
        Get a database connection from the pool.

        Returns:
            connection: A PostgreSQL database connection.

        Raises:
            DatabaseConnectionError: If unable to get a connection from the pool.
        """
        if not self._pool:
            raise DatabaseConnectionError("Connection pool not initialized")

        try:
            connection = self._pool.getconn()
            yield connection
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        finally:
            if connection:
                self._pool.putconn(connection)

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
