"""FastAPI dependencies. Tests swap these out via app.dependency_overrides."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Annotated

import psycopg
from fastapi import Depends

from src.answer.llm_client import LLMClientProtocol, get_llm_client
from src.db.connection import get_connection
from src.retrieval.embeddings import EmbedderProtocol, get_embedder

ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]


def connection_factory() -> ConnectionFactory:
    """Callable that opens a pooled DB connection as a context manager."""
    return get_connection


def llm_client() -> LLMClientProtocol:
    return get_llm_client()


def embedder() -> EmbedderProtocol:
    return get_embedder()


# Annotated aliases so routes declare dependencies without calling Depends() in defaults.
Connect = Annotated[ConnectionFactory, Depends(connection_factory)]
LLM = Annotated[LLMClientProtocol, Depends(llm_client)]
Embedder = Annotated[EmbedderProtocol, Depends(embedder)]
