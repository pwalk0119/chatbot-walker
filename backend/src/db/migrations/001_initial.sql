-- 001_initial: core schema for the PNW Policy & Process Q&A Chatbot (T009).
-- Mirrors specs/001-university-info-chatbot/data-model.md.

CREATE EXTENSION IF NOT EXISTS vector;

-- Enum types ---------------------------------------------------------------

CREATE TYPE document_campus AS ENUM ('Hammond', 'Westville', 'Both', 'N/A');
CREATE TYPE document_academic_level AS ENUM ('Undergraduate', 'Graduate', 'Both', 'N/A');
CREATE TYPE content_type AS ENUM ('html', 'pdf');
CREATE TYPE campus AS ENUM ('Hammond', 'Westville');
CREATE TYPE academic_level AS ENUM ('Undergraduate', 'Graduate');
CREATE TYPE conversation_status AS ENUM ('active', 'ended');
CREATE TYPE message_role AS ENUM ('student', 'chatbot');
CREATE TYPE contact_campus AS ENUM ('Hammond', 'Westville', 'Both');

-- Knowledge base -------------------------------------------------------------

CREATE TABLE source_documents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url          text NOT NULL UNIQUE,
    title               text NOT NULL,
    content_type        content_type NOT NULL,
    -- Markdown; HTML tables kept as Markdown tables, never flattened (FR-007)
    parsed_content      text NOT NULL,
    content_hash        text,
    campus              document_campus NOT NULL DEFAULT 'N/A',
    academic_level      document_academic_level NOT NULL DEFAULT 'N/A',
    -- 'evergreen' or a term such as 'Fall 2026'; past terms are excluded from retrieval (FR-005)
    term_applicability  text NOT NULL DEFAULT 'evergreen'
        CHECK (term_applicability = 'evergreen'
               OR term_applicability ~ '^(Winter|Spring|Summer|Fall) [0-9]{4}$'),
    -- Child page / attached PDF -> the top-level page it was reached from (FR-006)
    parent_document_id  uuid REFERENCES source_documents(id) ON DELETE SET NULL,
    last_ingested_at    timestamptz NOT NULL DEFAULT now(),
    last_verified_at    timestamptz
);

CREATE INDEX source_documents_parent_idx ON source_documents (parent_document_id);

CREATE TABLE document_chunks (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id  uuid NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    chunk_index         integer NOT NULL,
    chunk_text          text NOT NULL,
    -- Full Markdown table this chunk came from, so rows/columns are never scrambled (FR-007)
    context_text        text,
    embedding           vector(768) NOT NULL,
    UNIQUE (source_document_id, chunk_index)
);

CREATE INDEX document_chunks_embedding_idx
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Department / contact directory (FR-008) -----------------------------------

CREATE TABLE department_contacts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL UNIQUE,
    topics          text[] NOT NULL DEFAULT '{}',
    contact_method  text NOT NULL,
    campus          contact_campus
);

-- Conversations --------------------------------------------------------------

CREATE TABLE conversations (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at        timestamptz NOT NULL DEFAULT now(),
    -- Set once known, then reused for the rest of the conversation (FR-004, FR-013)
    campus            campus,
    academic_level    academic_level,
    status            conversation_status NOT NULL DEFAULT 'active',
    -- Question waiting on a clarifying answer (campus / academic level)
    pending_question  text
);

CREATE TABLE messages (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             message_role NOT NULL,
    text             text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    answer_id        uuid
);

CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);

CREATE TABLE answers (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id             uuid NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
    response_text          text NOT NULL,
    -- [{source_document_id, title, url}, ...] (FR-003)
    citations              jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(citations) = 'array'),
    escalated              boolean NOT NULL DEFAULT false,
    department_contact_id  uuid REFERENCES department_contacts(id),
    -- "Never guess" (FR-002/FR-003/FR-008): exactly one of
    --   (a) citations non-empty, or
    --   (b) escalated = true with a department_contact_id
    CONSTRAINT answers_cited_xor_escalated CHECK (
        (jsonb_array_length(citations) > 0)
        <> (escalated AND department_contact_id IS NOT NULL)
    ),
    CONSTRAINT answers_escalation_names_department CHECK (
        NOT escalated OR department_contact_id IS NOT NULL
    )
);

-- messages <-> answers reference each other; add the second FK once both tables exist.
ALTER TABLE messages
    ADD CONSTRAINT messages_answer_fk
    FOREIGN KEY (answer_id) REFERENCES answers(id) ON DELETE SET NULL;

-- Retention (FR-011) ---------------------------------------------------------

CREATE TABLE retained_transcripts (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Hashed, non-reversible; never points back to raw PII
    conversation_ref   text NOT NULL UNIQUE,
    deidentified_text  text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    purge_after        timestamptz NOT NULL,
    CONSTRAINT retained_transcripts_max_90_days
        CHECK (purge_after <= created_at + interval '90 days')
);

CREATE INDEX retained_transcripts_purge_idx ON retained_transcripts (purge_after);

-- Transcripts whose redaction pass still detected PII go here for human review
-- instead of silent storage; held under the same 90-day ceiling.
CREATE TABLE transcript_review_queue (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_ref  text NOT NULL,
    held_text         text NOT NULL,
    reason            text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    purge_after       timestamptz NOT NULL,
    CONSTRAINT transcript_review_queue_max_90_days
        CHECK (purge_after <= created_at + interval '90 days')
);
