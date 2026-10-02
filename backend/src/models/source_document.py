"""SourceDocument and DocumentChunk models (T012)."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.models.enums import ContentType, DocumentAcademicLevel, DocumentCampus

EVERGREEN = "evergreen"

# Order of terms within one calendar year.
_SEASON_ORDER = {"Winter": 0, "Spring": 1, "Summer": 2, "Fall": 3}
_TERM_RE = re.compile(r"^(Winter|Spring|Summer|Fall) (\d{4})$")


def parse_term(term: str) -> tuple[int, int]:
    """Turn 'Fall 2026' into a sortable (year, season) pair; raise ValueError otherwise."""
    match = _TERM_RE.match(term.strip())
    if not match:
        raise ValueError(f"invalid term {term!r}; expected e.g. 'Fall 2026' or 'evergreen'")
    season, year = match.groups()
    return int(year), _SEASON_ORDER[season]


class SourceDocument(BaseModel):
    id: UUID
    source_url: str
    title: str
    content_type: ContentType
    parsed_content: str
    content_hash: str | None = None
    campus: DocumentCampus = DocumentCampus.NOT_APPLICABLE
    academic_level: DocumentAcademicLevel = DocumentAcademicLevel.NOT_APPLICABLE
    term_applicability: str = EVERGREEN
    parent_document_id: UUID | None = None
    last_ingested_at: datetime
    last_verified_at: datetime | None = None

    @field_validator("term_applicability")
    @classmethod
    def _valid_term(cls, value: str) -> str:
        if value != EVERGREEN:
            parse_term(value)
        return value

    def is_current(self, current_term: str) -> bool:
        """False when this document is tied to a term that has already passed (FR-005).

        Evergreen content and current or upcoming terms are both current.
        """
        if self.term_applicability == EVERGREEN:
            return True
        return parse_term(self.term_applicability) >= parse_term(current_term)


class DocumentChunk(BaseModel):
    id: UUID
    source_document_id: UUID
    chunk_index: int
    chunk_text: str
    # The full Markdown table a chunk was drawn from, kept to avoid row/column scrambling (FR-007)
    context_text: str | None = None
    embedding: list[float] | None = None
