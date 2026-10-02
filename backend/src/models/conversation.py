"""Conversation and Message models (T013)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.models.enums import AcademicLevel, Campus, ConversationStatus, MessageRole


class Conversation(BaseModel):
    id: UUID
    started_at: datetime
    # Set once known, then reused for the rest of the conversation (FR-004, FR-013)
    campus: Campus | None = None
    academic_level: AcademicLevel | None = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    # Question waiting on a clarifying answer
    pending_question: str | None = None


class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    text: str
    created_at: datetime
    answer_id: UUID | None = None
