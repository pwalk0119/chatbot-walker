"""Phase 2 checkpoint: schema, migrations, seed data, health and conversation creation."""

from uuid import UUID

import psycopg
import pytest

from src.db import seed_contacts
from src.db.migrate import apply_migrations
from src.db.repositories import conversations
from src.models.enums import Campus, MessageRole


def test_migrations_are_idempotent(test_database_url):
    assert apply_migrations(test_database_url) == []


def test_health_is_ok(client):
    response = client.get("/api/chat/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "llm": "configured"}


def test_start_conversation(client):
    response = client.post("/api/chat/conversations")
    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body == {"id": body["id"], "campus": None, "academicLevel": None, "status": "active"}


def test_conversation_slots_persist(db):
    convo = conversations.create_conversation(db)
    conversations.update_slots(db, convo.id, campus=Campus.HAMMOND)
    # Updating the other slot leaves the stated campus alone (FR-004 reuse).
    updated = conversations.update_slots(db, convo.id, academic_level="Graduate")
    assert updated.campus == "Hammond"
    assert updated.academic_level == "Graduate"
    conversations.append_message(db, convo.id, MessageRole.STUDENT, "When is drop day?")
    assert [m.text for m in conversations.list_messages(db, convo.id)] == ["When is drop day?"]


def test_seed_contacts_is_repeatable(db):
    contacts = seed_contacts.load_contacts()
    assert {"Office of the Registrar", "Office of Financial Aid", "Dean of Students Office",
            "Academic Advising"} <= {c["name"] for c in contacts}
    seed_contacts.seed(db, contacts)
    seed_contacts.seed(db, contacts)
    count = db.execute("SELECT count(*) AS n FROM department_contacts").fetchone()["n"]
    assert count == len(contacts)


def _chatbot_message(db) -> UUID:
    convo = conversations.create_conversation(db)
    return conversations.append_message(db, convo.id, MessageRole.CHATBOT, "reply").id


def test_database_rejects_an_uncited_unescalated_answer(db):
    message_id = _chatbot_message(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO answers (message_id, response_text) VALUES (%s, 'a guess')",
            (message_id,),
        )


def test_database_accepts_cited_and_escalated_answers(db):
    db.execute(
        """INSERT INTO answers (message_id, response_text, citations)
           VALUES (%s, 'cited', '[{"title": "t", "url": "https://www.pnw.edu/"}]')""",
        (_chatbot_message(db),),
    )
    dept = db.execute(
        "INSERT INTO department_contacts (name, contact_method) "
        "VALUES ('Registrar', 'https://www.pnw.edu/registrar/') RETURNING id"
    ).fetchone()["id"]
    db.execute(
        """INSERT INTO answers (message_id, response_text, escalated, department_contact_id)
           VALUES (%s, 'escalated', true, %s)""",
        (_chatbot_message(db), dept),
    )


def test_database_caps_transcript_retention_at_90_days(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            """INSERT INTO retained_transcripts (conversation_ref, deidentified_text, purge_after)
               VALUES ('ref', 'text', now() + interval '91 days')"""
        )


def test_vector_column_round_trips(db):
    doc = db.execute(
        """INSERT INTO source_documents (source_url, title, content_type, parsed_content)
           VALUES ('https://www.pnw.edu/a', 'A', 'html', 'body') RETURNING id"""
    ).fetchone()["id"]
    vector = [0.0] * 768
    vector[0] = 1.0
    db.execute(
        "INSERT INTO document_chunks (source_document_id, chunk_index, chunk_text, embedding) "
        "VALUES (%s, 0, 'body', %s)",
        (doc, vector),
    )
    row = db.execute(
        "SELECT embedding <=> %s::vector AS distance FROM document_chunks", (vector,)
    ).fetchone()
    assert row["distance"] == pytest.approx(0.0)
