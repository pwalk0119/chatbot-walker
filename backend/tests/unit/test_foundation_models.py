"""Phase 2 checks for config, models and API schemas (no database needed)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.api.schemas import AnswerReply, ClarifyingQuestionReply, StudentMessageRequest
from src.config import ConfigError, Settings, get_settings
from src.models.answer import Answer, Citation
from src.models.source_document import SourceDocument, parse_term

NOW = datetime.now(UTC)


def make_doc(term: str) -> SourceDocument:
    return SourceDocument(
        id=uuid4(), source_url="https://www.pnw.edu/x", title="X", content_type="html",
        parsed_content="", term_applicability=term, last_ingested_at=NOW,
    )


# --- Config (T007) ---


def test_missing_required_settings_fail_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigError) as exc:
            get_settings()
        assert "DATABASE_URL is required" in str(exc.value)
        assert "ANTHROPIC_API_KEY is required" in str(exc.value)
    finally:
        get_settings.cache_clear()


def test_retention_days_cannot_exceed_90(monkeypatch):
    monkeypatch.setenv("RETENTION_DAYS", "91")
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigError, match="RETENTION_DAYS"):
            get_settings()
    finally:
        get_settings.cache_clear()


# --- SourceDocument.is_current (T012, FR-005) ---


@pytest.mark.parametrize(
    ("term", "current"),
    [
        ("evergreen", True),
        ("Fall 2026", True),     # the current term
        ("Spring 2027", True),   # upcoming
        ("Summer 2026", False),  # earlier the same year
        ("Fall 2025", False),    # a year ago
    ],
)
def test_is_current(term, current):
    assert make_doc(term).is_current("Fall 2026") is current


def test_invalid_term_is_rejected():
    with pytest.raises(ValidationError):
        make_doc("Autumn 26")
    with pytest.raises(ValueError):
        parse_term("2026 Fall")


# --- Answer invariant (T014) ---


def test_cited_answer_is_valid():
    Answer(id=uuid4(), message_id=uuid4(), response_text="...",
           citations=[Citation(title="Schedule", url="https://www.pnw.edu/registrar/")])


def test_escalated_answer_is_valid():
    Answer(id=uuid4(), message_id=uuid4(), response_text="...", escalated=True,
           department_contact_id=uuid4())


@pytest.mark.parametrize(
    "fields",
    [
        {},  # neither cited nor escalated: a guess
        {"escalated": True},  # escalated without a department
        {"escalated": True, "department_contact_id": uuid4(),
         "citations": [Citation(title="t", url="https://www.pnw.edu/")]},  # both
    ],
)
def test_invalid_answers_are_rejected(fields):
    with pytest.raises(ValidationError):
        Answer(id=uuid4(), message_id=uuid4(), response_text="...", **fields)


# --- API schemas (T016) ---


def test_answer_reply_requires_a_citation():
    with pytest.raises(ValidationError):
        AnswerReply(response_text="x", citations=[])


def test_schemas_use_contract_camel_case():
    reply = ClarifyingQuestionReply(prompt_text="Which campus?", slot="campus")
    assert reply.model_dump(mode="json") == {
        "type": "clarifying_question", "promptText": "Which campus?", "slot": "campus",
    }
    req = StudentMessageRequest.model_validate({"text": "hi", "statedCampus": "Hammond"})
    assert req.stated_campus == "Hammond"


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_message_text_is_rejected(text):
    with pytest.raises(ValidationError):
        StudentMessageRequest(text=text)
