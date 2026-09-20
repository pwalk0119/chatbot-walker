# Quickstart: University Policy & Process Q&A Chatbot

Validates the feature end-to-end against the acceptance scenarios in [spec.md](./spec.md). References [data-model.md](./data-model.md) and [contracts/chat-api.yaml](./contracts/chat-api.yaml) rather than duplicating their detail.

## Prerequisites

- Python 3.11+, Node/TypeScript toolchain for the widget
- PostgreSQL with the `pgvector` extension enabled
- An Anthropic API key (`ANTHROPIC_API_KEY`) with access to the Claude API
- A seed corpus: at minimum the sample pages/PDFs already reviewed in `Compiled Initial Corpus Review.pdf` (parking regulations + child pages, academic schedule, academic catalog, student handbook, classroom behavior policy, academic integrity policy, accessibility policy, information services policies)
- A seeded `DepartmentContact` table (Registrar, Financial Aid, Dean of Students Office, Academic Advising, at minimum)

## Setup

```bash
# 1. Provision storage
createdb pnw_chatbot
psql pnw_chatbot -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 2. Install backend deps and run migrations
cd backend && pip install -r requirements.txt
python -m src.db.migrate

# 3. Run ingestion against the seed corpus
python -m src.ingestion.run --config config/seed_corpus.yaml

# 4. Start the backend API
uvicorn src.api.main:app --reload

# 5. In a separate shell, build and serve the widget
cd frontend && npm install && npm run dev
```

## Validation scenarios

Run each of the following against the running backend (via the widget UI, or `curl`/an API client against `POST /api/chat/conversations` and `POST /api/chat/conversations/{id}/messages`).

### US1 — Direct answer with citation (P1)

1. Start a conversation; ask: *"When is the last day to drop a class?"*
2. **Expect**: `type: "answer"`, non-empty `citations` pointing at the academic-schedule source, and a date drawn from the *current* term (FR-005) — not a stale one from an older cached page.
3. Ask: *"How do I pay or appeal a parking ticket?"*
4. **Expect**: a single synthesized answer covering the full process, with citations from both the top-level parking page and any child page/PDF it drew from (FR-006) — not just a link back to the top-level page.

### US2 — Campus clarification (P2)

1. Start a new conversation; ask a question whose answer differs by campus (e.g., course availability for a course offered at only one campus).
2. **Expect**: `type: "clarifying_question"`, `slot: "campus"`.
3. Reply with a campus (e.g., "Hammond").
4. **Expect**: `type: "answer"` reflecting that campus's data.
5. Ask a second, different campus-dependent question in the same conversation.
6. **Expect**: no repeated clarifying question — the stated campus is reused (FR-004, Conversation.campus persists).

### US3 — Escalation instead of guessing (P3)

1. Start a conversation; ask something with no matching content in the corpus (e.g., a fabricated policy name).
2. **Expect**: `type: "escalation"`, a `department` naming a real office and contact method — never an `answer` with fabricated citations.
3. Ask a personalized/account-specific question (e.g., "why did I get error E4021 when registering?").
4. **Expect**: `type: "escalation"` directing to the Registrar/advisor, not an attempted diagnosis (FR-009).

## Cross-cutting checks

- **SC-002 (accuracy)**: run the representative common-question test set (add/drop, academic standing, grade appeals, financial aid deadlines, registration, contacts) through the API; assert ≥95% match official current policy with no factual errors.
- **SC-007 (accessibility)**: run `npm run test:a11y` (axe-core) against the built widget; zero critical/serious violations, then a manual pass before launch.
- **FR-011 (retention)**: insert a test conversation, run the purge job with a simulated clock >90 days later, and confirm the corresponding `RetainedTranscript` row is deleted and contains no raw PII prior to deletion.
- **FR-005 (no stale dates)**: re-run ingestion with a source page updated to a new term's deadlines and confirm the old term's `SourceDocument` row is excluded from "current" retrieval.

## Expected outcome

All scenarios above pass without manual intervention, confirming the chatbot behaves per spec.md's acceptance scenarios and the contract in `contracts/chat-api.yaml`.
