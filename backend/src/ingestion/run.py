"""Offline ingestion pipeline: crawl -> parse -> chunk -> embed -> store (T031).

Usage (from backend/):
    python -m src.ingestion.run                         # ingest every seed
    python -m src.ingestion.run --only academic-schedule
    python -m src.ingestion.run --dry-run               # parse and chunk only; no DB, no model
    python -m src.ingestion.run --force                 # re-embed even unchanged documents

Unchanged documents (same content hash) keep their existing chunks, so re-runs are
cheap. Each document is written in its own transaction.
"""

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from src.config import BACKEND_DIR, DATABASE_ONLY, ConfigError, get_settings
from src.ingestion.chunker import chunk_markdown
from src.ingestion.crawler import Crawler, SeedConfig
from src.ingestion.store import DocumentMetadata, chunk_count, replace_chunks, upsert_document
from src.models.enums import DocumentAcademicLevel, DocumentCampus
from src.models.source_document import EVERGREEN, parse_term

DEFAULT_CONFIG = BACKEND_DIR / "config" / "seed_corpus.yaml"
logger = logging.getLogger("ingest")


@dataclass
class Seed:
    name: str
    crawl: SeedConfig
    meta: DocumentMetadata


def load_seeds(path: Path) -> list[Seed]:
    data = yaml.safe_load(path.read_text()) or {}
    seeds = []
    for i, raw in enumerate(data.get("seeds") or [], start=1):
        name = raw.get("name") or f"seed-{i}"
        if not raw.get("url"):
            raise ValueError(f"seed {name!r} has no url")
        meta = DocumentMetadata(
            campus=DocumentCampus(raw.get("campus", "N/A")).value,
            academic_level=DocumentAcademicLevel(raw.get("academic_level", "N/A")).value,
            term=str(raw.get("term", EVERGREEN)),
        )
        if meta.term != EVERGREEN:
            parse_term(meta.term)  # raises on a malformed term
        crawl = SeedConfig(
            url=raw["url"],
            max_depth=int(raw.get("max_depth", 0)),
            follow=list(raw.get("follow") or []),
            follow_pdfs=bool(raw.get("follow_pdfs", True)),
            max_pages=int(raw.get("max_pages", 20)),
        )
        seeds.append(Seed(name=name, crawl=crawl, meta=meta))
    names = [s.name for s in seeds]
    if len(names) != len(set(names)):
        raise ValueError("seed names must be unique")
    return seeds


def run(seeds: list[Seed], database_url: str | None, *, dry_run: bool, force: bool,
        delay: float, crawler: Crawler | None = None, embedder=None) -> int:
    """Ingest the seeds. `crawler` and `embedder` can be injected (tests use fakes)."""
    crawler = crawler or Crawler(delay_seconds=delay)
    conn = None
    if not dry_run:
        if embedder is None:
            from src.retrieval.embeddings import get_embedder

            embedder = get_embedder()
        conn = psycopg.connect(database_url, row_factory=dict_row)
        register_vector(conn)

    rows: list[tuple[str, int, str, str, int, str]] = []
    totals = {"documents": 0, "chunks": 0, "embedded": 0}
    try:
        for seed in seeds:
            logger.info("crawling %s: %s", seed.name, seed.crawl.url)
            docs = crawler.crawl(seed.crawl)
            if not docs:
                logger.warning("%s: nothing ingested (see warnings above)", seed.name)
            ids_by_url = {}
            for doc in docs:
                page = doc.page
                chunks = chunk_markdown(page.markdown, page.title)
                totals["documents"] += 1
                totals["chunks"] += len(chunks)
                status = "parsed"
                if conn is not None:
                    with conn.transaction():
                        parent_id = ids_by_url.get(doc.parent_url)
                        doc_id, changed = upsert_document(conn, page, seed.meta, parent_id)
                        ids_by_url[page.url] = doc_id
                        if changed or force or chunk_count(conn, doc_id) != len(chunks):
                            vectors = embedder.embed_documents([c.text for c in chunks])
                            replace_chunks(conn, doc_id, chunks, vectors)
                            totals["embedded"] += len(chunks)
                            status = "stored"
                        else:
                            status = "unchanged"
                rows.append((seed.name, doc.depth, page.content_type, page.title,
                             len(chunks), status))
                logger.info("  [%s] depth %d %s: %s (%d chunks)", status, doc.depth,
                            page.content_type, page.url, len(chunks))
    finally:
        if conn is not None:
            conn.close()

    _print_summary(rows, totals, dry_run)
    return 0 if totals["documents"] else 1


def _print_summary(rows, totals, dry_run: bool) -> None:
    print()
    print(f"{'SEED':<30} {'D':>1} {'TYPE':<4} {'CHUNKS':>6}  {'STATUS':<9} TITLE")
    for name, depth, ctype, title, n, status in rows:
        print(f"{name:<30} {depth:>1} {ctype:<4} {n:>6}  {status:<9} {title[:60]}")
    print()
    verb = "parsed (dry run, nothing stored)" if dry_run else "ingested"
    print(f"{totals['documents']} documents {verb}; {totals['chunks']} chunks; "
          f"{totals['embedded']} chunks embedded and written this run")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="seed corpus YAML (default: config/seed_corpus.yaml)")
    parser.add_argument("--only", action="append", metavar="NAME",
                        help="ingest only this seed (repeatable)")
    parser.add_argument("--dry-run", action="store_true",
                        help="crawl, parse and chunk, but do not embed or store")
    parser.add_argument("--force", action="store_true",
                        help="re-embed documents even if their content is unchanged")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between requests to the same site (default 1.0)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("httpx", "httpcore", "pdfminer", "sentence_transformers", "trafilatura"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    database_url = None
    if not args.dry_run:
        try:
            database_url = get_settings(require=DATABASE_ONLY).database_url
        except ConfigError as exc:
            print(exc, file=sys.stderr)
            return 1

    seeds = load_seeds(args.config)
    if args.only:
        unknown = set(args.only) - {s.name for s in seeds}
        if unknown:
            print(f"unknown seed name(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        seeds = [s for s in seeds if s.name in args.only]

    started = time.monotonic()
    code = run(seeds, database_url, dry_run=args.dry_run, force=args.force, delay=args.delay)
    print(f"finished in {time.monotonic() - started:.1f}s")
    return code


if __name__ == "__main__":
    sys.exit(main())
