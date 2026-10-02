"""Answer and Citation models (T014)."""

from uuid import UUID

from pydantic import BaseModel, model_validator


class Citation(BaseModel):
    source_document_id: UUID | None = None
    title: str
    url: str


class Answer(BaseModel):
    id: UUID
    message_id: UUID
    response_text: str
    citations: list[Citation] = []
    escalated: bool = False
    department_contact_id: UUID | None = None

    @model_validator(mode="after")
    def _cited_xor_escalated(self) -> "Answer":
        # "Exactly one of 'has non-empty citations' or 'escalated = true with a
        # department_contact_id' MUST hold" (data-model.md; FR-002/FR-003/FR-008).
        cited = len(self.citations) > 0
        escalated_to_department = self.escalated and self.department_contact_id is not None
        if self.escalated and self.department_contact_id is None:
            raise ValueError("an escalated answer must name a department_contact_id")
        if cited == escalated_to_department:
            raise ValueError(
                "an answer must either carry citations or be escalated to a department, "
                "not both and not neither"
            )
        return self
