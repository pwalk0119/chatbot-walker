# Phase 1 Data Model: University Policy & Process Q&A Chatbot

Derived from the spec's Key Entities section, expanded with the fields and rules needed to satisfy the Functional Requirements and Clarifications. Conceptual model — not a literal schema — but shaped for direct translation into `pgvector`-backed Postgres tables.

## SourceDocument

A piece of official PNW content ingested into the knowledge base.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary identifier |
| `source_url` | string | Original page/PDF URL |
| `title` | string | Human-readable title, shown in citations (FR-003) |
| `content_type` | enum(`html`, `pdf`) | Drives which ingestion parser applies |
| `parsed_content` | text (Markdown) | Extracted content; HTML tables preserved as Markdown tables, not flattened (FR-007) |
| `campus` | enum(`Hammond`, `Westville`, `Both`, `N/A`) | Drives the FR-004 campus slot-filling check |
| `academic_level` | enum(`Undergraduate`, `Graduate`, `Both`, `N/A`) | Drives the FR-013 academic-level slot-filling check |
| `term_applicability` | string \| `evergreen` | e.g., `"Fall 2026"`; used to exclude expired term-specific content (FR-005) |
| `parent_document_id` | UUID, nullable | Links a child/linked page or attached PDF back to the top-level page it was reached from (FR-006) |
| `last_ingested_at` | timestamp | When this version was last fetched/parsed |
| `last_verified_at` | timestamp, nullable | When PNW staff last confirmed this content is current |
| `embedding` | vector | Chunk-level embeddings stored per retrievable chunk (see note below) |

**Note**: In practice a `SourceDocument` is chunked for retrieval (one or more embedded chunks per document, each retaining a back-reference to `SourceDocument.id` plus enough context — e.g., the full Markdown table a chunk was drawn from — to avoid the row/column-scrambling failure mode FR-007 exists to prevent).

**Validation rules**:
- A `SourceDocument` whose `term_applicability` names a past term MUST be excluded from "current" retrieval results (FR-005).
- `parent_document_id` chains MUST be followed when answering so that a top-level page's answer can include steps drawn from its children (FR-006).

## Conversation

A single student's chat session.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary identifier |
| `started_at` | timestamp | |
| `campus` | enum(`Hammond`, `Westville`), nullable | Set once known; persists for the rest of the conversation (FR-004, User Story 2 AC2) |
| `academic_level` | enum(`Undergraduate`, `Graduate`), nullable | Set once known; persists for the rest of the conversation (FR-013) |
| `status` | enum(`active`, `ended`) | |

**State transitions**: `active` (campus/level unset) → *(clarifying question asked and answered, if needed)* → `active` (campus/level set, reused for remaining turns) → `ended`.

## Message

One turn within a Conversation.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `conversation_id` | UUID | FK to Conversation |
| `role` | enum(`student`, `chatbot`) | |
| `text` | text | Raw turn text (student question, or chatbot's rendered reply) |
| `created_at` | timestamp | |
| `answer_id` | UUID, nullable | Set for `chatbot` role turns that carry a structured Answer |

## Answer

The structured result the chatbot produces for a student question.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `message_id` | UUID | FK to the `chatbot`-role Message it belongs to |
| `response_text` | text | The synthesized answer shown to the student |
| `citations` | list of `{source_document_id, title, url}` | MUST be non-empty for any substantive, non-escalated answer (FR-003) |
| `escalated` | boolean | True when FR-008 applies (no confident answer found) |
| `department_contact_id` | UUID, nullable | Required when `escalated = true`; names who the student should contact instead (FR-008) |

**Validation rules**:
- Exactly one of "has non-empty `citations`" or "`escalated = true` with a `department_contact_id`" MUST hold — an `Answer` is never both citation-less and non-escalated (this is the direct implementation of FR-002/FR-003/FR-008's "never guess" guarantee).

## DepartmentContact

An office or role the chatbot can direct a student to.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `name` | string | e.g., "Registrar", "Financial Aid", "Dean of Students Office", "Academic Advising" |
| `topics` | list of string | Topic tags used to match an escalation to the right office |
| `contact_method` | string | Link, email, or phone, as appropriate (FR-008; handoff is informational only per spec Assumptions) |
| `campus` | enum(`Hammond`, `Westville`, `Both`), nullable | For departments with campus-specific contact info |

## RetainedTranscript

The de-identified, time-limited record kept for answer-quality improvement (FR-011).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `conversation_ref` | string (hashed, non-reversible) | Does not point back to any raw PII |
| `deidentified_text` | text | Conversation content after the redaction pass (student IDs, emails, phone numbers, names removed) |
| `created_at` | timestamp | |
| `purge_after` | timestamp | MUST equal `created_at + 90 days`; enforced by a scheduled purge job (FR-011) |

**Validation rules**:
- `purge_after` MUST NOT exceed `created_at + 90 days`.
- `RetainedTranscript` rows MUST NOT contain values matched by the redaction pass; any detected PII blocks the write and routes to a review queue instead of silent storage.
