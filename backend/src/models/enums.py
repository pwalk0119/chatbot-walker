"""Shared enumerations; values match data-model.md and the database enum types (T011)."""

from enum import StrEnum


class Campus(StrEnum):
    """A student's campus (Conversation.campus)."""

    HAMMOND = "Hammond"
    WESTVILLE = "Westville"


class DocumentCampus(StrEnum):
    """Which campus a source document applies to (SourceDocument.campus)."""

    HAMMOND = "Hammond"
    WESTVILLE = "Westville"
    BOTH = "Both"
    NOT_APPLICABLE = "N/A"


class ContactCampus(StrEnum):
    """Campus a department contact serves (DepartmentContact.campus)."""

    HAMMOND = "Hammond"
    WESTVILLE = "Westville"
    BOTH = "Both"


class AcademicLevel(StrEnum):
    """A student's academic level (Conversation.academic_level)."""

    UNDERGRADUATE = "Undergraduate"
    GRADUATE = "Graduate"


class DocumentAcademicLevel(StrEnum):
    """Which academic level a source document applies to (SourceDocument.academic_level)."""

    UNDERGRADUATE = "Undergraduate"
    GRADUATE = "Graduate"
    BOTH = "Both"
    NOT_APPLICABLE = "N/A"


class ContentType(StrEnum):
    HTML = "html"
    PDF = "pdf"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class MessageRole(StrEnum):
    STUDENT = "student"
    CHATBOT = "chatbot"


class ReplyType(StrEnum):
    """ChatbotReply.type in contracts/chat-api.yaml."""

    ANSWER = "answer"
    CLARIFYING_QUESTION = "clarifying_question"
    ESCALATION = "escalation"


class Slot(StrEnum):
    """ClarifyingQuestionReply.slot in contracts/chat-api.yaml."""

    CAMPUS = "campus"
    ACADEMIC_LEVEL = "academicLevel"
