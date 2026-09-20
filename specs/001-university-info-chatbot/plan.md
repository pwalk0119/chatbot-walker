# Implementation Plan: University Policy & Process Q&A Chatbot

**Branch**: `001-university-info-chatbot` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-university-info-chatbot/spec.md`

## Summary

Build a retrieval-augmented chatbot, embeddable as a web widget on PNW's own pages, that answers student questions about university policies, deadlines, and processes directly (not just links), sourced only from an ingested corpus of official PNW web pages and policy PDFs. It asks for campus (Hammond/Westville) or academic level (undergrad/grad) when the answer depends on either, cites its sources, and — when it cannot find a confident answer — names the correct department/contact instead of guessing. Backend and ingestion pipeline in Python, answer generation via the Anthropic Claude API, retrieval via a self-hosted Postgres + pgvector store.

## Technical Context

**Language/Version**: Python 3.11+ (backend, ingestion), TypeScript (embeddable widget frontend)

**Primary Dependencies**: Anthropic Python SDK (Claude API for answer generation); FastAPI (backend API); `sentence-transformers` (self-hosted embeddings); `psycopg`/`pgvector` client; `trafilatura` + `BeautifulSoup` (HTML extraction) and `pdfplumber`/`PyMuPDF` (PDF extraction) for ingestion; `axe-core` (automated WCAG 2.1 AA checks) for the widget

**Storage**: PostgreSQL with the `pgvector` extension — single self-hosted datastore for vector embeddings, Source Document metadata, Department/Contact directory, and de-identified conversation transcripts (FR-011)

**Testing**: `pytest` (backend unit/integration/contract tests), a fixed representative question set for accuracy validation against SC-002, `axe-core` automated pass plus a manual review for the SC-007 accessibility audit

**Target Platform**: Containerized web service (Linux) exposing a chat API, consumed by an embeddable JS/TS widget loaded on PNW web pages

**Project Type**: Web application (backend service + frontend widget)

**Performance Goals**: p95 chat response latency (retrieval + generation) under 8 seconds per turn; full answer delivered well within SC-001's 2-minute end-to-end budget

**Constraints**: No student login or access to individual academic records (per spec Assumptions); retained transcripts de-identified and purged after ≤90 days (FR-011); widget UI conforms to WCAG 2.1 AA (FR-012); answers MUST NOT state information absent from the ingested corpus (FR-002)

**Scale/Scope**: Initial corpus spans all topics identified in source review (Dean of Students topics, parking, academic catalog/prerequisites, student handbook, classroom behavior, academic integrity, accessibility, information services policies); design for at least 300 concurrent conversations during peak periods (e.g., registration week) as a starting capacity target

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` in this repository is still the unfilled template (placeholder principle names/descriptions, no ratified content) — there are no concrete project principles to gate against. No violations are possible against an empty constitution; this gate is treated as **N/A / pass by default**. If the team ratifies a real constitution later, this plan should be re-checked against it.

## Project Structure

### Documentation (this feature)

```text
specs/001-university-info-chatbot/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── chat-api.yaml
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── ingestion/        # HTML/PDF fetchers, child-link crawler, table-preserving chunker
│   ├── retrieval/        # embeddings, pgvector queries, campus/level-aware filtering
│   ├── answer/           # prompt construction, Claude API calls, citation assembly, escalation logic
│   ├── privacy/          # de-identification pass + 90-day retention purge job
│   ├── models/           # SourceDocument, Conversation, Answer, DepartmentContact
│   └── api/               # FastAPI routes (chat endpoint, health)
└── tests/
    ├── contract/          # chat-api.yaml contract tests
    ├── integration/        # end-to-end story tests (US1/US2/US3 acceptance scenarios)
    └── unit/

frontend/
├── src/
│   ├── widget/            # embeddable chat widget (mountable script/component)
│   ├── components/
│   └── services/           # chat API client
└── tests/
    ├── unit/
    └── a11y/                # axe-core WCAG 2.1 AA checks
```

**Structure Decision**: Web application split (`backend/` + `frontend/`) — the backend owns ingestion, retrieval, answer generation, and privacy/retention; the frontend is the embeddable widget consumed by PNW web pages. This matches the "embeddable web widget" delivery surface decision and keeps the corpus/LLM logic server-side, away from the public client.

## Complexity Tracking

*No entries — the Constitution Check gate is N/A (no ratified constitution principles to violate), so no complexity justification is required.*
