"""DepartmentContact model (T015)."""

from uuid import UUID

from pydantic import BaseModel

from src.models.enums import ContactCampus


class DepartmentContact(BaseModel):
    id: UUID
    name: str
    # Topic tags used to match an escalation to the right office
    topics: list[str] = []
    # Link, email, or phone; the handoff is informational only (spec Assumptions)
    contact_method: str
    campus: ContactCampus | None = None
