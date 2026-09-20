# Phase 0 Research: University Policy & Process Q&A Chatbot

Resolves the technical unknowns not already settled by direct decision (LLM provider: Anthropic Claude API; stack: Python; delivery surface: embeddable web widget; retrieval store: self-hosted vector store — all confirmed with the project owner before this research).

## 1. RAG orchestration approach

- **Decision**: Custom, lightweight orchestration built directly on the Anthropic Python SDK — no general-purpose agent framework (LangChain/LlamaIndex).
- **Rationale**: The spec's hardest requirements are control-flow requirements, not generic RAG requirements: campus/academic-level slot-filling must happen *before* retrieval (FR-004, FR-013), every substantive answer must carry a citation (FR-003), and low-confidence retrieval must escalate to a department instead of answering (FR-008, FR-002). These are easiest to guarantee and test explicitly with direct control over the retrieve → check-confidence → (ask-clarifying-question | answer-with-citations | escalate) flow, rather than working around a framework's own abstractions.
- **Alternatives considered**: LangChain and LlamaIndex — both speed up generic RAG prototyping, but their higher-level chains make it harder to enforce and unit-test the specific escalation/citation guarantees that are this project's top risk (Dean of Students Office's stated #1 concern: never give incorrect policy information).

## 2. Embedding model

- **Decision**: Self-hosted open-source embedding model via `sentence-transformers` (e.g., a `bge-base`-class model tuned for retrieval).
- **Rationale**: Keeps embeddings under PNW's own infrastructure, consistent with the chosen self-hosted vector store and with FR-011's stance that student-related data stays controlled and minimal. No added per-call vendor cost or third-party data flow for routine ingestion/embedding traffic.
- **Alternatives considered**: Voyage AI embeddings (Anthropic's recommended pairing, likely higher retrieval quality but a new paid vendor and external data flow), OpenAI embeddings (same tradeoff, and a different vendor than the chosen LLM). Either can be revisited later if self-hosted embedding quality proves insufficient against SC-002's 95% accuracy bar.

## 3. Vector store engine

- **Decision**: PostgreSQL with the `pgvector` extension, used as the single datastore for embeddings and relational data.
- **Rationale**: One database serves vector similarity search *and* the relational metadata already required — Source Document metadata (campus, term applicability, last-verified date), the Department/Contact directory, and de-identified conversation transcripts (FR-011). A single self-hosted system is less operational surface than running a dedicated vector database alongside a separate relational store.
- **Alternatives considered**: Chroma (simple embedded API, but would be a second datastore to operate and secure alongside whatever holds relational data).

## 4. Ingestion & content parsing (FR-006, FR-007, FR-010)

- **Decision**: `trafilatura`/`BeautifulSoup` for HTML extraction with a bounded recursive crawler that follows child links and attached PDFs from a seed page (e.g., the parking regulations page → payment/appeal sub-pages → forms); `pdfplumber`/`PyMuPDF` for PDF text and layout extraction; HTML tables converted to Markdown tables (preserving row/column pairing) *before* chunking, rather than passed through a naive fixed-size text splitter.
- **Rationale**: Directly answers the two concrete ingestion failure modes the corpus review identified: (a) a naive top-level scrape misses the parking ticket payment/appeal steps that live on child pages and PDFs, and (b) a naive text splitter scrambles per-term deadline/refund tables in the academic schedule.
- **Alternatives considered**: Fixed-size recursive character splitting (industry-default for generic RAG) — explicitly rejected for date/deadline content because the corpus review demonstrated it produces mismatched rows/columns.

## 5. Campus / academic-level slot-filling (FR-004, FR-013)

- **Decision**: A small per-conversation state object (`campus`, `academic_level`, both nullable) checked before issuing any retrieval query flagged as campus- or level-dependent; populated either by an explicit student statement or by asking a clarifying question once, then reused for the rest of the conversation.
- **Rationale**: Matches User Story 2's acceptance scenarios exactly (ask once, then reuse) without requiring login or a stored student profile, consistent with the spec's assumption that the chatbot does not access individual student records.
- **Alternatives considered**: Inferring campus/level from a logged-in student profile — rejected, contradicts the "no login, no personal record access" assumption already in the spec.

## 6. De-identification & retention (FR-011)

- **Decision**: Retained transcripts pass through a redaction step (pattern matching for student IDs/emails/phone numbers, plus a lightweight NER pass for names) before being written to storage; a scheduled job purges any transcript older than 90 days.
- **Rationale**: Directly implements the clarified requirement — anonymized retention only, capped at 90 days, used solely for answer-quality improvement.
- **Alternatives considered**: Manual redaction review (doesn't scale to production traffic), storing raw transcripts (rejected outright — contradicts the clarification and creates unnecessary FERPA exposure).

## 7. Accessibility validation (FR-012, SC-007)

- **Decision**: Automated `axe-core` checks run in the frontend test suite on every widget build, plus a manual accessibility review pass before launch.
- **Rationale**: SC-007 requires an independent audit with zero critical/serious violations; automated tools catch a large share of WCAG issues cheaply and continuously, but are known to miss some categories (e.g., meaningful focus order, some ARIA misuse), so a manual pass is needed for a genuine pre-launch sign-off.
- **Alternatives considered**: Automated-only checks — rejected as insufficient for a compliance-grade audit claim.

## 8. Performance & scale targets

- **Decision**: Target p95 per-turn response latency (retrieval + generation) under 8 seconds; design initial capacity for at least 300 concurrent conversations during peak periods (e.g., registration week, add/drop deadline days).
- **Rationale**: SC-001's 2-minute end-to-end budget is generous for a single answer, but a tighter per-turn target keeps the interaction feeling like a real conversation. 300 concurrent sessions is a reasonable starting planning number for a two-campus university's peak week without over-provisioning; it should be revisited once real usage data is available post-launch.
- **Alternatives considered**: Leaving performance/scale unspecified — rejected, the plan's Constraints section needs a concrete number to size the backend and database against.

**Output**: All `NEEDS CLARIFICATION` items from the Technical Context are resolved above; no unresolved unknowns remain blocking Phase 1.
