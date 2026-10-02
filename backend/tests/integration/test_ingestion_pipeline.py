"""T031: crawl -> parse -> chunk -> embed -> store, end to end against the test database."""

from src.ingestion.crawler import Crawler
from src.ingestion.run import load_seeds, run
from tests.unit.test_crawler import SITE, FakeSite, make_pdf

SITE_SCHEDULE = (
    "text/html",
    b"""<html><body><main><h1>Academic Schedule</h1>
    <div class="accordion"><button class="accordion__toggle">Fall '26</button>
    <div class="accordion__content"><table>
      <tr><th>Event</th><th>Date</th></tr>
      <tr><td>Last Day to Drop a Full-Term Course</td><td>November 13</td></tr>
    </table></div></div></main></body></html>""",
)


def write_config(tmp_path):
    config = tmp_path / "seeds.yaml"
    config.write_text(
        """
seeds:
  - name: parking
    url: https://www.pnw.edu/parking/regulations/
    campus: Both
    max_depth: 2
    follow: [/public-safety/forms/]
  - name: schedule
    url: https://www.pnw.edu/registrar/academic-schedule/
"""
    )
    return config


def test_pipeline_stores_documents_and_embedded_chunks(
    tmp_path, test_database_url, db, fake_embedder, monkeypatch
):
    monkeypatch.setitem(SITE, "https://www.pnw.edu/registrar/academic-schedule/", SITE_SCHEDULE)
    seeds = load_seeds(write_config(tmp_path))
    crawler = Crawler(fetch=FakeSite(make_pdf()), delay_seconds=0)

    assert run(seeds, test_database_url, dry_run=False, force=False, delay=0,
               crawler=crawler, embedder=fake_embedder) == 0

    docs = db.execute(
        "SELECT source_url, content_type, campus, parent_document_id FROM source_documents "
        "ORDER BY last_ingested_at, source_url"
    ).fetchall()
    assert len(docs) == 4  # regulations, forms page, appeal PDF, schedule
    by_url = {d["source_url"]: d for d in docs}
    pdf = by_url["https://www.pnw.edu/public-safety/forms/appeal.pdf"]
    assert pdf["content_type"] == "pdf"
    assert pdf["campus"] == "Both"  # inherited from the seed
    forms_id = db.execute(
        "SELECT id FROM source_documents WHERE source_url = %s",
        ("https://www.pnw.edu/public-safety/forms/",),
    ).fetchone()["id"]
    assert pdf["parent_document_id"] == forms_id  # FR-006 chain recorded

    chunks = db.execute(
        "SELECT chunk_text, context_text, vector_dims(embedding) AS dims FROM document_chunks"
    ).fetchall()
    assert all(c["dims"] == 768 for c in chunks)
    table_chunk = next(c for c in chunks if "November 13" in c["chunk_text"])
    assert "| Last Day to Drop a Full-Term Course | November 13 |" in table_chunk["chunk_text"]
    assert table_chunk["context_text"] is not None

    # The stored vectors are searchable: the drop-date question finds the schedule chunk.
    query = fake_embedder.embed_query("last day to drop a full-term course")
    best = db.execute(
        "SELECT chunk_text FROM document_chunks ORDER BY embedding <=> %s::vector LIMIT 1",
        (query,),
    ).fetchone()
    assert "November 13" in best["chunk_text"]


def test_rerun_skips_unchanged_documents(
    tmp_path, test_database_url, db, fake_embedder, monkeypatch, capsys
):
    monkeypatch.setitem(SITE, "https://www.pnw.edu/registrar/academic-schedule/", SITE_SCHEDULE)
    seeds = load_seeds(write_config(tmp_path))
    for _ in range(2):
        crawler = Crawler(fetch=FakeSite(make_pdf()), delay_seconds=0)
        run(seeds, test_database_url, dry_run=False, force=False, delay=0,
            crawler=crawler, embedder=fake_embedder)
    out = capsys.readouterr().out
    assert "0 chunks embedded and written this run" in out
    count = db.execute("SELECT count(*) AS n FROM source_documents").fetchone()["n"]
    assert count == 4  # upserted, not duplicated
