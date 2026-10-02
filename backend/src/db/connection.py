"""PostgreSQL connection pool with pgvector type registration (T008)."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config import get_settings

_pool: ConnectionPool | None = None


def _configure(conn: psycopg.Connection) -> None:
    # Lets psycopg send and receive pgvector columns as Python lists / numpy arrays.
    # Requires the `vector` extension, which migration 001 creates.
    register_vector(conn)


def get_pool() -> ConnectionPool:
    """Return the process-wide pool, opening it on first use."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=get_settings().database_url,
            min_size=1,
            max_size=10,
            # Fail fast instead of psycopg's 30 s default: a turn has an 8 s budget.
            timeout=5.0,
            kwargs={"row_factory": dict_row},
            configure=_configure,
            open=True,
        )
    return _pool


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Borrow a connection; commits on success, rolls back on error."""
    with get_pool().connection() as conn:
        yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
