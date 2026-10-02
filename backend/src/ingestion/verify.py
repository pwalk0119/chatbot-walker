"""Inspect what the offline pipeline stored in the vector database.

Usage (from backend/):
    python -m src.ingestion.verify                              # documents and chunk counts
    python -m src.ingestion.verify --query "last day to drop a class"   # nearest chunks

The --query option embeds the question with the same model and runs a pgvector
cosine-distance search, showing that the stored vectors are searchable.
"""

import argparse
import sys

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from src.config import DATABASE_ONLY, ConfigError, get_settings


def show_documents(conn: psycopg.Connection) -> int:
    docs = conn.execute(
        """
        SELECT d.title, d.content_type, d.source_url, d.campus, d.term_applicability,
               (d.parent_document_id IS NOT NULL) AS is_child,
               count(c.id) AS chunks,
               max(vector_dims(c.embedding)) AS dims
          FROM source_documents d
          LEFT JOIN document_chunks c ON c.source_document_id = d.id
         GROUP BY d.id
         ORDER BY d.last_ingested_at, d.source_url
        """
    ).fetchall()
    print(f"{'TYPE':<4} {'CHUNKS':>6} {'DIMS':>4}  {'CHILD':<5} TITLE / URL")
    for d in docs:
        print(f"{d['content_type']:<4} {d['chunks']:>6} {d['dims'] or '-':>4}  "
              f"{'yes' if d['is_child'] else '':<5} {d['title'][:70]}")
        print(f"{'':<23}{d['source_url']}")
    totals = conn.execute(
        "SELECT (SELECT count(*) FROM source_documents) AS docs, "
        "(SELECT count(*) FROM document_chunks) AS chunks"
    ).fetchone()
    print(f"\n{totals['docs']} documents, {totals['chunks']} embedded chunks in the database")
    return totals["docs"]


def search(conn: psycopg.Connection, query: str, k: int) -> None:
    from src.retrieval.embeddings import get_embedder

    vector = get_embedder().embed_query(query)
    rows = conn.execute(
        """
        SELECT d.title, d.source_url, c.chunk_text, c.embedding <=> %s::vector AS distance
          FROM document_chunks c
          JOIN source_documents d ON d.id = c.source_document_id
         ORDER BY c.embedding <=> %s::vector
         LIMIT %s
        """,
        (vector, vector, k),
    ).fetchall()
    print(f'\nTop {k} chunks for: "{query}"\n')
    for rank, r in enumerate(rows, start=1):
        snippet = " ".join(r["chunk_text"].split())[:220]
        print(f"{rank}. distance {r['distance']:.3f}  {r['title']}\n   {r['source_url']}\n"
              f"   {snippet}…\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the ingested vector database.")
    parser.add_argument("--query", help="run a similarity search for this question")
    parser.add_argument("-k", type=int, default=3, help="results to show with --query")
    args = parser.parse_args(argv)
    try:
        settings = get_settings(require=DATABASE_ONLY)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        register_vector(conn)
        count = show_documents(conn)
        if args.query:
            search(conn, args.query, args.k)
    return 0 if count else 1


if __name__ == "__main__":
    sys.exit(main())
