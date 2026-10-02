"""Write ingested documents and their embedded chunks to Postgres + pgvector (T031)."""

import hashlib
from dataclasses import dataclass
from uuid import UUID

import psycopg

from src.ingestion.chunker import Chunk
from src.ingestion.html_extractor import ExtractedPage


@dataclass
class DocumentMetadata:
    campus: str = "N/A"
    academic_level: str = "N/A"
    term: str = "evergreen"


def content_hash(page: ExtractedPage) -> str:
    return hashlib.sha256(f"{page.title}\n{page.markdown}".encode()).hexdigest()


def upsert_document(
    conn: psycopg.Connection,
    page: ExtractedPage,
    meta: DocumentMetadata,
    parent_id: UUID | None,
) -> tuple[UUID, bool]:
    """Insert or update a source document; return (id, content_changed)."""
    digest = content_hash(page)
    existing = conn.execute(
        "SELECT id, content_hash FROM source_documents WHERE source_url = %s", (page.url,)
    ).fetchone()
    row = conn.execute(
        """
        INSERT INTO source_documents
            (source_url, title, content_type, parsed_content, content_hash,
             campus, academic_level, term_applicability, parent_document_id, last_ingested_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (source_url) DO UPDATE SET
            title = EXCLUDED.title,
            content_type = EXCLUDED.content_type,
            parsed_content = EXCLUDED.parsed_content,
            content_hash = EXCLUDED.content_hash,
            campus = EXCLUDED.campus,
            academic_level = EXCLUDED.academic_level,
            term_applicability = EXCLUDED.term_applicability,
            parent_document_id = EXCLUDED.parent_document_id,
            last_ingested_at = now()
        RETURNING id
        """,
        (page.url, page.title, page.content_type, page.markdown, digest,
         meta.campus, meta.academic_level, meta.term, parent_id),
    ).fetchone()
    doc_id = row["id"] if isinstance(row, dict) else row[0]
    changed = existing is None or _value(existing, "content_hash", 1) != digest
    return doc_id, changed


def chunk_count(conn: psycopg.Connection, doc_id: UUID) -> int:
    row = conn.execute(
        "SELECT count(*) AS n FROM document_chunks WHERE source_document_id = %s", (doc_id,)
    ).fetchone()
    return _value(row, "n", 0)


def replace_chunks(
    conn: psycopg.Connection,
    doc_id: UUID,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError(f"{len(chunks)} chunks but {len(embeddings)} embeddings")
    conn.execute("DELETE FROM document_chunks WHERE source_document_id = %s", (doc_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO document_chunks
                (source_document_id, chunk_index, chunk_text, context_text, embedding)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [(doc_id, c.index, c.text, c.context_text, e) for c, e in zip(chunks, embeddings,
                                                                          strict=True)],
        )


def _value(row, key: str, index: int):
    return row[key] if isinstance(row, dict) else row[index]
