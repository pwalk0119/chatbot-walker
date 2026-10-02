"""Shared pytest fixtures (T023).

Database tests run against a throwaway database, `pnw_chatbot_test` by default on the
docker-compose Postgres. Point them elsewhere with TEST_DATABASE_URL. If no Postgres is
reachable, database tests are skipped (not failed) with a message saying why.
"""

import hashlib
import math
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager

# Configure the app for tests *before* anything imports src.config.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pnw_chatbot_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # never let tests touch the real database
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pgvector.psycopg import register_vector  # noqa: E402
from psycopg import sql  # noqa: E402
from psycopg.conninfo import conninfo_to_dict, make_conninfo  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from src.api import deps  # noqa: E402
from src.db.migrate import apply_migrations  # noqa: E402
from src.retrieval.embeddings import EMBEDDING_DIM  # noqa: E402

APP_TABLES = [
    "answers",
    "messages",
    "conversations",
    "document_chunks",
    "source_documents",
    "department_contacts",
    "retained_transcripts",
    "transcript_review_queue",
]


# --- Fakes ---------------------------------------------------------------------


class FakeLLM:
    """Stands in for the Claude client: records calls, returns a canned reply."""

    def __init__(self, reply: str = "Fake answer [1]") -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def generate(self, system: str, messages: list[dict]) -> str:
        self.calls.append({"system": system, "messages": messages})
        return self.reply


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words get similar vectors."""

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.sha256(word.encode()).hexdigest(), 16) % EMBEDDING_DIM
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


# --- Database ------------------------------------------------------------------


def _admin_url(url: str) -> str:
    params = conninfo_to_dict(url)
    params["dbname"] = "postgres"
    return make_conninfo(**params)


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """Create a fresh test database with all migrations applied; drop it afterwards."""
    dbname = conninfo_to_dict(TEST_DATABASE_URL).get("dbname")
    if not dbname or dbname == "postgres":
        pytest.exit("TEST_DATABASE_URL must name a dedicated test database", returncode=2)
    try:
        admin = psycopg.connect(_admin_url(TEST_DATABASE_URL), autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at {TEST_DATABASE_URL} ({exc}); start it with "
                    "`docker compose up -d` or set TEST_DATABASE_URL")
    drop = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname))
    with admin:
        admin.execute(drop)
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    apply_migrations(TEST_DATABASE_URL)
    yield TEST_DATABASE_URL
    with psycopg.connect(_admin_url(TEST_DATABASE_URL), autocommit=True) as admin:
        admin.execute(drop)


@pytest.fixture
def connection_factory(test_database_url: str) -> Iterator[deps.ConnectionFactory]:
    """Same shape as the app's pooled get_connection, against the test database.

    Every app table is emptied after each test so tests never see each other's rows.
    """

    @contextmanager
    def connect() -> Iterator[psycopg.Connection]:
        with psycopg.connect(test_database_url, row_factory=dict_row) as conn:
            register_vector(conn)
            yield conn  # psycopg commits on clean exit, rolls back on error

    yield connect
    with psycopg.connect(test_database_url) as conn:
        conn.execute(
            sql.SQL("TRUNCATE {} CASCADE").format(
                sql.SQL(", ").join(sql.Identifier(t) for t in APP_TABLES)
            )
        )


@pytest.fixture
def db(connection_factory: deps.ConnectionFactory) -> Iterator[psycopg.Connection]:
    """A single connection for direct repository/SQL tests."""
    with connection_factory() as conn:
        yield conn


# --- App -----------------------------------------------------------------------


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def client(
    connection_factory: deps.ConnectionFactory,
    fake_llm: FakeLLM,
    fake_embedder: FakeEmbedder,
) -> Iterator[TestClient]:
    """API client wired to the test database and fake LLM/embedder (no network calls)."""
    from src.api.main import create_app

    app = create_app()
    app.dependency_overrides[deps.connection_factory] = lambda: connection_factory
    app.dependency_overrides[deps.llm_client] = lambda: fake_llm
    app.dependency_overrides[deps.embedder] = lambda: fake_embedder
    with TestClient(app) as test_client:
        yield test_client
