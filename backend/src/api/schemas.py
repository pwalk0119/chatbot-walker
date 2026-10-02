"""Request/response schemas matching contracts/chat-api.yaml exactly (T016).

Python attributes are snake_case; JSON uses the contract's camelCase names via aliases.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from src.models.enums import AcademicLevel, Campus, ConversationStatus, Slot


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ConversationOut(ApiModel):
    id: UUID
    campus: Campus | None = None
    academic_level: AcademicLevel | None = None
    status: ConversationStatus


class StudentMessageRequest(ApiModel):
    text: str = Field(min_length=1)
    # Optional client hints; the backend still applies FR-004/FR-013 slot-filling itself.
    stated_campus: Campus | None = None
    stated_academic_level: AcademicLevel | None = None

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class CitationOut(ApiModel):
    source_document_id: UUID | None = None
    title: str
    url: AnyUrl


class DepartmentContactOut(ApiModel):
    name: str
    contact_method: str


class AnswerReply(ApiModel):
    type: Literal["answer"] = "answer"
    response_text: str
    # MUST be non-empty for every "answer" reply (FR-003)
    citations: list[CitationOut] = Field(min_length=1)


class ClarifyingQuestionReply(ApiModel):
    type: Literal["clarifying_question"] = "clarifying_question"
    prompt_text: str
    slot: Slot


class EscalationReply(ApiModel):
    type: Literal["escalation"] = "escalation"
    explanation_text: str
    department: DepartmentContactOut


ChatbotReply = Annotated[
    AnswerReply | ClarifyingQuestionReply | EscalationReply,
    Field(discriminator="type"),
]
