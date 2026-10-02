"""Apply SQL migrations in order (T010).

Usage (from backend/):  python -m src.db.migrate
"""

import sys
from pathlib import Path

import psycopg

from src.config import ConfigError, get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Arbitrary constant so two migrators running at once take turns instead of colliding.
_ADVISORY_LOCK_ID = 7_301_001


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def apply_migrations(database_url: str) -> list[str]:
    """Apply every pending migration; return the filenames applied this run."""
    applied_now: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_ID,))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename    text PRIMARY KEY,
                    applied_at  timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            done = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
            for path in migration_files():
                if path.name in done:
                    continue
                # Each file and its bookkeeping row commit together, or not at all.
                with conn.transaction():
                    conn.execute(path.read_text())
                    conn.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
                    )
                applied_now.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_ID,))
    return applied_now


def main() -> int:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    applied = apply_migrations(settings.database_url)
    if applied:
        for name in applied:
            print(f"applied {name}")
    else:
        print("database is up to date; no migrations applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
