# chatbot-walker

A retrieval-augmented (RAG) chatbot that answers Purdue University Northwest (PNW)
students' questions about policies, deadlines and processes, using only official PNW
web pages and PDFs, and citing them. Specification and plan:
[`specs/001-university-info-chatbot/`](specs/001-university-info-chatbot/).

This README covers the **offline pipeline**: the part that turns PNW pages and PDFs into
embedded chunks in a PostgreSQL + pgvector database.

## Offline pipeline

```
seed_corpus.yaml ─► crawl ─► parse ─────────────► chunk ─► embed ──────────► store
                    │        │                    │        │                 │
                    │        HTML → Markdown      │        bge-base-en-v1.5  PostgreSQL + pgvector
                    │        PDF  → Markdown      │        768-dim vectors   source_documents
                    │        tables kept as       │                          document_chunks (HNSW)
                    │        Markdown tables      heading-aware,
                    child pages + PDFs            never splits a table row
```

| Stage | Code | What it does |
|---|---|---|
| Crawl | [`crawler.py`](backend/src/ingestion/crawler.py) | Fetches each seed and, within per-seed limits, the child pages and PDFs it links to (e.g. parking regulations → forms page → violation appeal PDF). Records each child's parent. Obeys robots.txt, waits between requests, and skips bot-challenged pages. |
| Parse HTML | [`html_extractor.py`](backend/src/ingestion/html_extractor.py) | Converts the page's main content to Markdown. Keeps text inside collapsed accordions (where PNW puts per-term deadlines), turns accordion toggles into headings, and renders every `<table>` as a Markdown table so dates stay paired with their events. Drops navigation, footers, scripts and share widgets. |
| Parse PDF | [`pdf_extractor.py`](backend/src/ingestion/pdf_extractor.py) | pdfplumber: bold/large lines become headings, wrapped lines are rejoined into paragraphs, ruled tables become Markdown tables. PyMuPDF fallback. |
| Chunk | [`chunker.py`](backend/src/ingestion/chunker.py) | Splits at headings and packs whole blocks into chunks of ≤1,200 characters (within the embedding model's 512-token window). Each chunk starts with its heading path, e.g. `Academic Schedule > Fall '26`. Large tables are split between rows with the header repeated, and the full table is stored alongside as `context_text`. |
| Embed | [`embeddings.py`](backend/src/retrieval/embeddings.py) | Self-hosted `BAAI/bge-base-en-v1.5` via sentence-transformers (768 dimensions, normalized). |
| Store | [`store.py`](backend/src/ingestion/store.py), [`001_initial.sql`](backend/src/db/migrations/001_initial.sql) | Upserts `source_documents` (URL, title, campus, academic level, term, parent) and replaces their `document_chunks` (`vector(768)` with an HNSW cosine index). Unchanged documents (same content hash) are skipped on re-runs. |
| Run | [`run.py`](backend/src/ingestion/run.py) | CLI that drives the stages above for every seed in [`seed_corpus.yaml`](backend/config/seed_corpus.yaml). |
| Verify | [`verify.py`](backend/src/ingestion/verify.py) | CLI that lists what is stored and runs a pgvector similarity search. |

### Ingested corpus

The seeds come from the team's corpus review (`Compiled Initial Corpus Review.pdf`).
A full run ingests **13 documents (11 web pages, 2 PDFs) as 192 embedded chunks**:

| Seed | Documents ingested |
|---|---|
| `parking-regulations` | Regulations and Enforcement → Forms → Parking/Traffic Violation Appeal Form (PDF) |
| `academic-schedule` | Academic Schedule, Refund and Withdrawal Schedule, Final Exam Schedule |
| `academic-integrity-policy` | Academic Integrity Policy |
| `accessibility` | Accessibility at PNW |
| `student-handbook` | Student Handbook |
| `classroom-behavior-policy` | Classroom Behavior Policy (PDF) |
| `information-services-policies` | Policies, Procedures and Forms; Administrative Rights Procedure; Security Exceptions Procedure |

Two sources from the corpus review are not ingested. The student handbook PDF it
names now returns 404, so its current HTML page is used instead. The `catalog.pnw.edu`
pages answer automated requests with an AWS WAF bot challenge, and the crawler does not
try to get past bot protection. Details are in
[`seed_corpus.yaml`](backend/config/seed_corpus.yaml).

## Running it

### 1. Prerequisites

- Python 3.11+
- PostgreSQL with the pgvector extension. The easiest way is Docker Desktop:
  ```bash
  docker compose up -d
  ```
  This starts `pgvector/pgvector:pg16` on port 5432 with a `pnw_chatbot` database
  ([`docker-compose.yml`](docker-compose.yml)). Without Docker, Homebrew works too:
  `brew install postgresql@16 pgvector`, then `createdb pnw_chatbot`.
- Internet access to pnw.edu, and to Hugging Face for the one-time model download (~440 MB).

### 2. Install and configure

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The pipeline needs only `DATABASE_URL` from `.env`. The default matches
`docker-compose.yml`. No Anthropic API key is needed for ingestion.

### 3. Create the schema

```bash
python -m src.db.migrate
```

### 4. Ingest

```bash
python -m src.ingestion.run
```

Useful options: `--dry-run` (crawl, parse and chunk without embedding or storing),
`--only academic-schedule` (one seed), `--force` (re-embed unchanged documents).

Output of a full run (2026-10-02, PostgreSQL 16.2 + pgvector 0.6.2):

```
SEED                           D TYPE CHUNKS  STATUS    TITLE
parking-regulations            0 html     56  stored    Regulations and Enforcement
parking-regulations            1 html      1  stored    Forms
parking-regulations            2 pdf       3  stored    Parking/Traffic Violation Appeal Form
academic-schedule              0 html     22  stored    Academic Schedule
academic-schedule              1 html      8  stored    Refund and Withdrawal Schedule
academic-schedule              1 html      4  stored    Final Exam Schedule
academic-integrity-policy      0 html     17  stored    Academic Integrity Policy
accessibility                  0 html     26  stored    Accessibility at PNW
student-handbook               0 html      5  stored    Student Handbook
classroom-behavior-policy      0 pdf      19  stored    FSD 20-15 Classroom Behavior Policy
information-services-policies  0 html     23  stored    Policies, Procedures and Forms
information-services-policies  1 html      3  stored    Administrative Rights Procedure
information-services-policies  1 html      5  stored    Security Exceptions Procedure

13 documents ingested; 192 chunks; 192 chunks embedded and written this run
```

(`D` is crawl depth: 0 = seed, 1 = linked from the seed, 2 = one level further.)

### 5. Verify what was stored

```bash
python -m src.ingestion.verify --query "How do I appeal a parking ticket?"
```

This lists every stored document with its chunk count and vector dimensions, then
embeds the question and runs a pgvector cosine search:

```
13 documents, 192 embedded chunks in the database

Top 3 chunks for: "How do I appeal a parking ticket?"

1. distance 0.230  Parking/Traffic Violation Appeal Form
   https://www.pnw.edu/public-safety/wp-content/uploads/sites/84/2022/03/Parking-TrafficViolationAppealForm.pdf
   Parking/Traffic Violation Appeal Form > Purdue University Northwest Parking/Traffic Violation Appeal Form Reason for appeal: …
```

You can also inspect the tables directly:

```bash
psql postgresql://postgres:postgres@localhost:5432/pnw_chatbot \
  -c "SELECT d.title, count(*) AS chunks, max(vector_dims(c.embedding)) AS dims
        FROM document_chunks c JOIN source_documents d ON d.id = c.source_document_id
       GROUP BY d.title ORDER BY chunks DESC;"
```

## Tests

```bash
cd backend && pytest
```

The database tests use a throwaway `pnw_chatbot_test` database on the same server, and
they are skipped if no Postgres is running. The pipeline tests use a fake website and a
fake embedder, so they need no network access and no model download. Coverage includes
HTML and PDF extraction, chunking, crawling rules, and an end-to-end
crawl → store → similarity-search run.
