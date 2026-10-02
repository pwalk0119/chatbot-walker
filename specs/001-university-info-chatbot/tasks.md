---

description: "Task list for the University Policy & Process Q&A Chatbot"
---

# Tasks: University Policy & Process Q&A Chatbot

**Input**: Design documents from `/specs/001-university-info-chatbot/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/chat-api.yaml, quickstart.md

**Tests**: Included. plan.md specifies `pytest` contract/integration tests (`backend/tests/contract/`, `backend/tests/integration/` for "US1/US2/US3 acceptance scenarios"), and FR-012/SC-007 require automated `axe-core` checks. quickstart.md also requires a retention purge test and an SC-002 accuracy test set.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Every task names its exact file path(s)

## Path Conventions

Web application split per plan.md: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`. Python modules are run from `backend/` (e.g., `python -m src.db.migrate`), matching quickstart.md.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the directory layout from plan.md: `backend/src/{ingestion,retrieval,answer,privacy,models,api,api/routes,db,db/migrations,db/repositories}`, `backend/tests/{contract,integration,unit}`, `backend/config/`, `frontend/src/{widget,components,services}`, `frontend/tests/{unit,a11y}`; add an empty `__init__.py` to `backend/src/` and every Python package directory under it, and to `backend/tests/` and its subdirectories
- [X] T002 Create `backend/requirements.txt` (anthropic, fastapi, uvicorn[standard], pydantic, pydantic-settings, psycopg[binary,pool], pgvector, sentence-transformers, trafilatura, beautifulsoup4, pdfplumber, pymupdf, httpx, pyyaml, pytest, pytest-asyncio, ruff) and `backend/pyproject.toml` declaring `requires-python = ">=3.11"`, pytest config (`testpaths = ["tests"]`), and ruff config (line length 100, target py311)
- [X] T003 [P] Initialize the widget project: `frontend/package.json` (Vite + TypeScript, no UI framework; the widget is a vanilla custom element), `frontend/tsconfig.json` (strict), `frontend/vite.config.ts` (library build emitting a single embeddable `pnw-chatbot.js`), and npm scripts `dev`, `build`, `test` (Vitest + jsdom), `test:a11y` (Vitest running `frontend/tests/a11y/` with `axe-core`), `lint`
- [X] T004 [P] Configure frontend linting/formatting in `frontend/eslint.config.js` and `frontend/.prettierrc` (TypeScript-ESLint recommended rules)
- [X] T005 [P] Create `backend/.env.example` with `DATABASE_URL`, `ANTHROPIC_API_KEY`, `LLM_MODEL=claude-opus-5-5`, `LLM_EFFORT=low`, `EMBEDDING_MODEL=BAAI/bge-base-en-v1.5`, `CURRENT_TERM` (e.g. `Fall 2026`), `RETENTION_DAYS=90`, `ALLOWED_WIDGET_ORIGINS`; and a root `.gitignore` covering `.env`, `__pycache__/`, `.venv/`, `node_modules/`, `dist/`, `.DS_Store`
- [X] T006 [P] Create `docker-compose.yml` at repo root running Postgres with pgvector (`pgvector/pgvector:pg16` image, database `pnw_chatbot`, port 5432, named volume) for local development

**Checkpoint**: Both projects install cleanly (`pip install -r backend/requirements.txt`, `npm install` in `frontend/`), and `docker compose up -d` gives a reachable Postgres.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Implement settings loading in `backend/src/config.py` using pydantic-settings, reading every variable in `backend/.env.example`; fail fast with a clear error if `DATABASE_URL` or `ANTHROPIC_API_KEY` is missing
- [X] T008 Implement a psycopg connection pool with pgvector type registration in `backend/src/db/connection.py` (`get_pool()`, `get_connection()` context manager)
- [X] T009 Write the initial schema in `backend/src/db/migrations/001_initial.sql`: `CREATE EXTENSION IF NOT EXISTS vector`; tables `source_documents` (campus enum(`Hammond`, `Westville`, `Both`, `N/A`); academic_level enum(`Undergraduate`, `Graduate`, `Both`, `N/A`); content_type enum(`html`, `pdf`); `term_applicability` string or `evergreen`; nullable `parent_document_id` self-FK; `last_ingested_at`; nullable `last_verified_at`), `document_chunks` (FK to source_documents, `chunk_text`, `context_text` holding the full Markdown table a chunk came from, `embedding vector(768)`, HNSW cosine index), `conversations` (campus enum(`Hammond`, `Westville`) nullable; academic_level enum(`Undergraduate`, `Graduate`) nullable; status enum(`active`, `ended`); nullable `pending_question` text), `messages` (role enum(`student`, `chatbot`); nullable `answer_id`), `answers` (`citations` JSONB; `escalated` boolean; nullable `department_contact_id`; CHECK that exactly one of "citations non-empty" or "escalated = true AND department_contact_id IS NOT NULL" holds), `department_contacts` (`topics` text[]; campus enum(`Hammond`, `Westville`, `Both`) nullable), `retained_transcripts` (`conversation_ref` hashed string; CHECK `purge_after <= created_at + interval '90 days'`), and `transcript_review_queue`
- [X] T010 Implement the migration runner in `backend/src/db/migrate.py` (runnable as `python -m src.db.migrate`): applies `backend/src/db/migrations/*.sql` in order and records applied files in a `schema_migrations` table so reruns are no-ops
- [X] T011 [P] Define shared enums (`Campus`, `DocumentCampus`, `AcademicLevel`, `DocumentAcademicLevel`, `ContentType`, `ConversationStatus`, `MessageRole`, `ReplyType`, `Slot`) in `backend/src/models/enums.py`, values matching data-model.md exactly
- [X] T012 [P] Create `SourceDocument` and `DocumentChunk` models in `backend/src/models/source_document.py` per data-model.md, including an `is_current(current_term)` helper that returns False when `term_applicability` names a past term (FR-005)
- [X] T013 [P] Create `Conversation` and `Message` models in `backend/src/models/conversation.py` per data-model.md
- [X] T014 [P] Create the `Answer` and `Citation` models in `backend/src/models/answer.py`, with a validator enforcing: "Exactly one of 'has non-empty `citations`' or '`escalated = true` with a `department_contact_id`' MUST hold"
- [X] T015 [P] Create the `DepartmentContact` model in `backend/src/models/department_contact.py` per data-model.md
- [X] T016 [P] Create API request/response schemas in `backend/src/api/schemas.py` matching `contracts/chat-api.yaml` exactly (camelCase field aliases: `academicLevel`, `statedCampus`, `responseText`, `promptText`, `explanationText`, `contactMethod`, `sourceDocumentId`; `ChatbotReply` as a discriminated union on `type`; `StudentMessageRequest.text` with `minLength: 1`; `AnswerReply.citations` with `minItems: 1`)
- [X] T017 Create the FastAPI app in `backend/src/api/main.py`: CORS restricted to `ALLOWED_WIDGET_ORIGINS`, structured logging, a JSON error handler, and router registration
- [X] T018 Implement `GET /api/chat/health` in `backend/src/api/routes/health.py`, returning 200 only when the database is reachable and the Anthropic client is configured
- [X] T019 [P] Implement the embedding service in `backend/src/retrieval/embeddings.py`: loads `EMBEDDING_MODEL` once via sentence-transformers and exposes `embed_documents(texts)` and `embed_query(text)` (normalized 768-dim vectors)
- [X] T020 [P] Implement a thin Anthropic client wrapper in `backend/src/answer/llm_client.py` (`generate(system, messages) -> str` using `LLM_MODEL` and `LLM_EFFORT`), with timeouts and retries so a turn stays within the 8-second p95 target
- [X] T021 Implement the conversation repository in `backend/src/db/repositories/conversations.py` (create, get, update slots/status, append message) and `POST /api/chat/conversations` in `backend/src/api/routes/chat.py` returning 201 with a `Conversation` body
- [X] T022 Seed department contacts: `backend/config/department_contacts.yaml` (at minimum Registrar, Financial Aid, Dean of Students Office, Academic Advising, each with `topics` and `contact_method`) and a loader `backend/src/db/seed_contacts.py` runnable as `python -m src.db.seed_contacts`
- [X] T023 [P] Create shared pytest fixtures in `backend/tests/conftest.py`: an isolated test database with migrations applied, a FastAPI `TestClient`, a fake LLM client and a deterministic fake embedder injected through FastAPI dependency overrides
- [X] T024 [P] Implement the typed chat API client in `frontend/src/services/chatApi.ts` (`startConversation()`, `sendMessage(conversationId, text, hints?)`), with TypeScript types mirroring `contracts/chat-api.yaml`

**Checkpoint**: `python -m src.db.migrate` creates the schema, the API starts with `uvicorn src.api.main:app`, `/api/chat/health` returns 200, and `POST /api/chat/conversations` creates a conversation.

---

## Phase 3: User Story 1 - Get a direct answer to a common policy or deadline question (Priority: P1) 🎯 MVP

**Goal**: A student asks a common policy/deadline question and gets a direct, current, cited answer synthesized from the official corpus, including processes spread across child pages and PDFs.

**Independent Test**: Ask "When is the last day to drop a class?" and "How do I pay or appeal a parking ticket?"; each returns `type: "answer"` with non-empty citations, a current-term date, and a complete multi-step process (quickstart.md, US1).

### Tests for User Story 1

- [ ] T025 [P] [US1] Contract test in `backend/tests/contract/test_chat_api.py`: `POST /api/chat/conversations` returns 201 + `Conversation`; `POST .../messages` returns 404 for an unknown id, 422 for empty `text`, and an `AnswerReply` with `citations` of `minItems: 1` for an answerable question
- [ ] T026 [P] [US1] Integration test in `backend/tests/integration/test_us1_direct_answer.py` covering US1 acceptance scenarios 1–3: direct answer plus citation; a past-term document is never cited as current; the parking-ticket answer cites both the parent page and a child page/PDF

### Implementation for User Story 1

- [X] T027 [P] [US1] Implement the HTML extractor in `backend/src/ingestion/html_extractor.py`: trafilatura for main content, BeautifulSoup to convert every `<table>` into a Markdown table that keeps row/column pairing (FR-007), and to include content from expandable sections/tabs present in the DOM (FR-010); returns Markdown plus discovered child links and PDF links
- [X] T028 [P] [US1] Implement the PDF extractor in `backend/src/ingestion/pdf_extractor.py` with pdfplumber (tables emitted as Markdown tables) and a PyMuPDF text fallback
- [X] T029 [US1] Implement the bounded crawler in `backend/src/ingestion/crawler.py`: from a seed URL, follows same-site child links and attached PDFs up to a configured depth, and sets `parent_document_id` on every child so parent chains can be followed later (FR-006)
- [X] T030 [US1] Implement the table-preserving chunker in `backend/src/ingestion/chunker.py`: splits on headings, never splits inside a Markdown table, and stores the full source table in `context_text` for any chunk drawn from a table (FR-007)
- [X] T031 [US1] Implement the ingestion runner `backend/src/ingestion/run.py` (`python -m src.ingestion.run --config config/seed_corpus.yaml`) and `backend/config/seed_corpus.yaml` listing the seed sources from the corpus review (parking regulations, academic schedule, academic catalog, student handbook, classroom behavior, academic integrity, accessibility, information services policies), each with `campus`, `academic_level`, and `term_applicability`; the runner upserts `source_documents` and re-embeds changed `document_chunks`
- [ ] T032 [US1] Implement retrieval in `backend/src/retrieval/search.py`: pgvector cosine search returning the top-k chunks with similarity scores, excluding documents whose `term_applicability` is a past term relative to `CURRENT_TERM` (FR-005), and expanding results to include parent/child documents in the same `parent_document_id` chain (FR-006)
- [ ] T033 [US1] Implement the grounded prompt builder in `backend/src/answer/prompt.py`: a system prompt instructing Claude to answer only from the supplied numbered source excerpts (FR-002), give a direct step-by-step answer rather than a link (FR-001, FR-006), keep table rows intact (FR-007), and tag every claim with the excerpt number(s) it came from
- [ ] T034 [US1] Implement citation assembly in `backend/src/answer/citations.py`: map the excerpt numbers the model used to `{source_document_id, title, url}` citations, dropping any number the model invented that was never supplied
- [ ] T035 [US1] Implement the answer orchestrator in `backend/src/answer/orchestrator.py`: retrieve → build prompt → generate → assemble citations → persist the student `Message`, chatbot `Message`, and `Answer` → return an `AnswerReply`
- [ ] T036 [US1] Implement `POST /api/chat/conversations/{conversationId}/messages` in `backend/src/api/routes/chat.py` calling the orchestrator, with 404 for an unknown conversation and 422 for empty text
- [ ] T037 [US1] Implement the embeddable custom element `<pnw-chatbot>` in `frontend/src/widget/index.ts`: registers the element, reads `data-api-base` from its attributes, and starts a conversation on first open
- [ ] T038 [US1] Implement chat UI components in `frontend/src/components/chat-window.ts`, `frontend/src/components/message-list.ts`, and `frontend/src/components/citation-list.ts`: text input + send button, message history, and cited source links rendered under each answer
- [ ] T039 [US1] Make the widget meet WCAG 2.1 AA (FR-012) in `frontend/src/components/chat-window.ts`: labeled input and buttons, `aria-live="polite"` region for new replies, full keyboard operation with visible focus, focus trapped while open and returned to the launcher on close, AA color contrast
- [ ] T040 [P] [US1] Automated accessibility test in `frontend/tests/a11y/widget.a11y.test.ts`: render the widget with a mocked answer + citations, run axe-core, and fail on any `critical` or `serious` violation (SC-007)

**Checkpoint**: User Story 1 is fully functional — ingest the seed corpus, then the US1 quickstart scenarios pass through both the API and the widget.

---

## Phase 4: User Story 2 - Get campus-specific answers when the answer depends on campus (Priority: P2)

**Goal**: When an answer differs by campus (Hammond/Westville) or academic level (Undergraduate/Graduate), the chatbot asks once, then reuses the stated value for the rest of the conversation.

**Independent Test**: Ask a campus-dependent question → `type: "clarifying_question"`, `slot: "campus"`; reply "Hammond" → campus-correct `answer`; ask a second campus-dependent question → no repeated clarifying question (quickstart.md, US2).

### Tests for User Story 2

- [ ] T041 [P] [US2] Contract test in `backend/tests/contract/test_clarifying_reply.py`: a campus-dependent question returns a `ClarifyingQuestionReply` with `promptText` and `slot` in `[campus, academicLevel]`
- [ ] T042 [P] [US2] Integration test in `backend/tests/integration/test_us2_campus_clarification.py` covering US2 acceptance scenarios 1–2 plus the academic-level equivalent (FR-013): ask once, answer uses the stated value, follow-up questions do not re-ask

### Implementation for User Story 2

- [ ] T043 [US2] Implement slot logic in `backend/src/answer/slots.py`: `detect_required_slots(chunks)` flags `campus` when relevant chunks carry differing `Hammond`/`Westville` values and `academicLevel` when they carry differing `Undergraduate`/`Graduate` values; `parse_stated_slots(text)` extracts a campus or level stated in free text
- [ ] T044 [US2] Extend retrieval in `backend/src/retrieval/search.py` with optional `campus` and `academic_level` filters that keep matching documents plus those tagged `Both` or `N/A`
- [ ] T045 [US2] Integrate slot-filling into `backend/src/answer/orchestrator.py`: apply `statedCampus`/`statedAcademicLevel` hints and parsed statements to the conversation; if a required slot is unset, store the question in `conversations.pending_question` and return a `ClarifyingQuestionReply`; when the student answers, persist the slot and answer the pending question with filtered retrieval (FR-004, FR-013)
- [ ] T046 [US2] Update `backend/src/answer/prompt.py` so that, when course/prerequisite excerpts come from several fragments or campus tags, the model combines them into one clear summary for the student's stated campus (FR-010)
- [ ] T047 [P] [US2] Implement `frontend/src/components/clarifying-prompt.ts`: shows `promptText` with accessible quick-reply buttons (Hammond / Westville or Undergraduate / Graduate) that send the choice as both message text and the matching `stated*` hint; wire it into `frontend/src/components/message-list.ts`

**Checkpoint**: User Stories 1 and 2 both work on their own; campus- and level-dependent questions are clarified once and then reused.

---

## Phase 5: User Story 3 - Get routed to the right department instead of a wrong or guessed answer (Priority: P3)

**Goal**: When the chatbot has no confident answer, or the question is personalized/account-specific or off-topic, it says so and names the right department and how to reach it, and never guesses.

**Independent Test**: Ask about a fabricated policy and "why did I get error E4021 when registering?"; both return `type: "escalation"` with a real department and contact method, never an `answer` (quickstart.md, US3).

### Tests for User Story 3

- [ ] T048 [P] [US3] Contract test in `backend/tests/contract/test_escalation_reply.py`: an unanswerable question returns an `EscalationReply` with `explanationText` and `department.name` / `department.contactMethod`
- [ ] T049 [P] [US3] Integration test in `backend/tests/integration/test_us3_escalation.py` covering US3 acceptance scenarios 1–2 plus an off-topic question, and asserting no persisted `Answer` is ever both citation-less and non-escalated (SC-003)

### Implementation for User Story 3

- [ ] T050 [US3] Implement the confidence gate in `backend/src/answer/confidence.py`: escalate when the top retrieval similarity is below a configurable threshold, when the model returns an explicit "insufficient information" marker (added to the system prompt in `backend/src/answer/prompt.py`), or when citation assembly yields zero valid citations
- [ ] T051 [US3] Implement personalized and off-topic detection in `backend/src/answer/intent.py`: classify each question as `policy`, `personalized` (account-specific errors, individual records, filling out a plan of study, per FR-009), or `off_topic`, before retrieval
- [ ] T052 [US3] Implement department routing in `backend/src/answer/department_router.py`: match the question to a `DepartmentContact` by `topics` (preferring the conversation's campus when a contact is campus-specific), falling back to the Dean of Students Office
- [ ] T053 [US3] Integrate escalation into `backend/src/answer/orchestrator.py`: personalized, off-topic, and low-confidence paths return an `EscalationReply` and persist an `Answer` with `escalated = true` and `department_contact_id` set (FR-008, FR-009)
- [ ] T054 [P] [US3] Implement `frontend/src/components/escalation-card.ts` showing the explanation and the department name with a clickable contact method (mailto:/tel:/link as appropriate); wire it into `frontend/src/components/message-list.ts`

**Checkpoint**: All three user stories work independently; the bot never returns an uncited, non-escalated answer.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Privacy/retention, accuracy validation, conflict handling, and launch readiness across all stories

- [ ] T055 [P] Implement de-identification in `backend/src/privacy/redact.py`: regex redaction of student IDs, emails, and phone numbers plus a lightweight NER pass for person names; returns redacted text and a `pii_remaining` flag
- [ ] T056 Implement transcript retention in `backend/src/privacy/transcripts.py`: when a conversation ends, redact it, store a `RetainedTranscript` with a hashed non-reversible `conversation_ref` and `purge_after = created_at + 90 days`, and route to `transcript_review_queue` instead of storing whenever `pii_remaining` is true (FR-011)
- [ ] T057 Implement the purge job in `backend/src/privacy/purge.py` (`python -m src.privacy.purge`): deletes `retained_transcripts` past `purge_after`, and also deletes raw `conversations`/`messages`/`answers` older than `RETENTION_DAYS`
- [ ] T058 [P] Unit tests in `backend/tests/unit/test_retention.py`: redaction removes each PII type; a transcript with a simulated clock more than 90 days later is purged; a write with remaining PII goes to the review queue (quickstart.md FR-011 check)
- [ ] T059 Handle conflicting sources in `backend/src/retrieval/search.py` and `backend/src/answer/prompt.py`: when excerpts disagree on a date or value, prefer the most recently verified current-term source, and when still unresolved, acknowledge the conflict and name the department that can confirm (spec Edge Cases)
- [ ] T060 [P] Build the SC-002 accuracy evaluation: `backend/tests/eval/common_questions.yaml` (add/drop, academic standing, grade appeals, financial aid deadlines, registration, contacts, each with its expected official answer) and `backend/tests/eval/run_eval.py` that reports the match rate against the 95% target
- [ ] T061 [P] Add `backend/Dockerfile` (Python 3.11 slim, runs `uvicorn src.api.main:app`) and a backend service in `docker-compose.yml`
- [ ] T062 [P] Write the repo `README.md` setup and run instructions (database, migrations, contact seeding, ingestion, API, widget embed snippet), consistent with quickstart.md
- [ ] T063 [P] Create the manual accessibility review checklist `specs/001-university-info-chatbot/checklists/accessibility.md` (screen reader pass, focus order, zoom to 200%, reduced motion) for the SC-007 pre-launch audit
- [ ] T064 Run every scenario in `specs/001-university-info-chatbot/quickstart.md` end to end and record results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; start immediately
- **Foundational (Phase 2)**: Depends on Setup; BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational; extends US1's orchestrator, retrieval, and prompt (T032, T033, T035), so in practice follows US1
- **User Story 3 (Phase 5)**: Depends on Foundational; extends US1's orchestrator and prompt (T033, T035), so in practice follows US1. Independent of US2
- **Polish (Phase 6)**: Depends on the user stories you intend to ship

### Key Task Dependencies

- T002 → T007 → T008 → T009 → T010 (config and DB before schema and migrations)
- T011 → T012–T015 (enums before models); T016 needs T011
- T017 → T018, T021 (app before routes)
- T027, T028 → T029 → T030 → T031 (extractors → crawler → chunker → runner)
- T019 + T031 → T032 → T035 → T036 (embeddings + ingested data → retrieval → orchestrator → route)
- T024 → T037 → T038 → T039 → T040 (API client → widget → UI → a11y → axe test)
- T043, T044 → T045; T050, T051, T052 → T053
- T055 → T056 → T057 → T058

### Parallel Opportunities

- Setup: T003, T004, T005, T006 in parallel once T001 is done
- Foundational: T011 first, then T012–T016 in parallel; T019, T020, T023, T024 in parallel
- US1: T025, T026, T027, T028 in parallel; frontend T037–T040 can proceed alongside backend T029–T036
- US2: T041, T042, T047 in parallel
- US3: T048, T049, T054 in parallel
- US2 and US3 can run in parallel by different developers once US1 is done
- Polish: T055, T058, T060, T061, T062, T063 in parallel

---

## Parallel Example: User Story 1

```bash
# Tests and extractors together:
Task: "Contract test in backend/tests/contract/test_chat_api.py"
Task: "Integration test in backend/tests/integration/test_us1_direct_answer.py"
Task: "HTML extractor in backend/src/ingestion/html_extractor.py"
Task: "PDF extractor in backend/src/ingestion/pdf_extractor.py"

# Frontend alongside backend retrieval/answer work:
Task: "Custom element <pnw-chatbot> in frontend/src/widget/index.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks all stories)
3. Complete Phase 3: User Story 1
4. **Stop and validate**: run the US1 quickstart scenarios
5. Demo if ready

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add US1 → validate → demo (MVP)
3. Add US2 → validate campus/level clarification → demo
4. Add US3 → validate escalation → demo
5. Polish → retention, accuracy eval, accessibility audit → launch readiness

---

## Notes

- [P] tasks touch different files and have no dependencies on incomplete tasks
- Commit after each task or logical group
- Stop at any checkpoint to validate a story on its own
- The escalation invariant (T009 CHECK constraint, T014 validator, T053) is the direct safeguard for the Dean of Students Office's top concern; don't loosen it
