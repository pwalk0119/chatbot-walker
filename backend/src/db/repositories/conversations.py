"""Conversation and message persistence (T021)."""

from uuid import UUID

import psycopg

from src.models.conversation import Conversation, Message
from src.models.enums import AcademicLevel, Campus, ConversationStatus, MessageRole

_COLUMNS = "id, started_at, campus, academic_level, status, pending_question"


def create_conversation(conn: psycopg.Connection) -> Conversation:
    row = conn.execute(
        f"INSERT INTO conversations DEFAULT VALUES RETURNING {_COLUMNS}"
    ).fetchone()
    return Conversation(**row)


def get_conversation(conn: psycopg.Connection, conversation_id: UUID) -> Conversation | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM conversations WHERE id = %s", (conversation_id,)
    ).fetchone()
    return Conversation(**row) if row else None


def update_slots(
    conn: psycopg.Connection,
    conversation_id: UUID,
    *,
    campus: Campus | None = None,
    academic_level: AcademicLevel | None = None,
) -> Conversation:
    """Record a stated campus and/or academic level. Passing None leaves a slot unchanged."""
    row = conn.execute(
        f"""
        UPDATE conversations
           SET campus = COALESCE(%s, campus),
               academic_level = COALESCE(%s, academic_level)
         WHERE id = %s
     RETURNING {_COLUMNS}
        """,
        (campus, academic_level, conversation_id),
    ).fetchone()
    return Conversation(**row)


def set_pending_question(
    conn: psycopg.Connection, conversation_id: UUID, question: str | None
) -> None:
    conn.execute(
        "UPDATE conversations SET pending_question = %s WHERE id = %s",
        (question, conversation_id),
    )


def set_status(
    conn: psycopg.Connection, conversation_id: UUID, status: ConversationStatus
) -> None:
    conn.execute(
        "UPDATE conversations SET status = %s WHERE id = %s", (status, conversation_id)
    )


def append_message(
    conn: psycopg.Connection,
    conversation_id: UUID,
    role: MessageRole,
    text: str,
    answer_id: UUID | None = None,
) -> Message:
    row = conn.execute(
        """
        INSERT INTO messages (conversation_id, role, text, answer_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id, conversation_id, role, text, created_at, answer_id
        """,
        (conversation_id, role, text, answer_id),
    ).fetchone()
    return Message(**row)


def list_messages(conn: psycopg.Connection, conversation_id: UUID) -> list[Message]:
    rows = conn.execute(
        """
        SELECT id, conversation_id, role, text, created_at, answer_id
          FROM messages WHERE conversation_id = %s ORDER BY created_at, id
        """,
        (conversation_id,),
    ).fetchall()
    return [Message(**r) for r in rows]
