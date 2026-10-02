"""Self-hosted sentence-transformers embeddings (T019)."""

from functools import lru_cache
from typing import Protocol

from src.config import get_settings

# Must match document_chunks.embedding vector(768) in migration 001.
EMBEDDING_DIM = 768

# BGE models embed queries better with this instruction prefix; documents get none.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbedderProtocol(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class Embedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._query_prefix = _BGE_QUERY_PREFIX if "bge" in model_name.lower() else ""

    def _load(self):
        if self._model is None:
            # Imported lazily: loading torch is slow and only needed on first use.
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name)
            dim = model.get_sentence_embedding_dimension()
            if dim != EMBEDDING_DIM:
                raise RuntimeError(
                    f"{self.model_name} produces {dim}-dim vectors but the database "
                    f"expects {EMBEDDING_DIM}; choose a {EMBEDDING_DIM}-dim model"
                )
            self._model = model
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load().encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self._load().encode(self._query_prefix + text, normalize_embeddings=True)
        return vector.tolist()


@lru_cache
def get_embedder() -> Embedder:
    """Process-wide embedder; the model loads once, on first use."""
    return Embedder(get_settings().embedding_model)
