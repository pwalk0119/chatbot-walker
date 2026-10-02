"""Application settings, loaded from environment variables and backend/.env (T007)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Settings with no safe default. The API needs both; each CLI asks only for what it uses
# (ingestion, migrations and seeding need the database but never call Claude).
REQUIRED = ("DATABASE_URL", "ANTHROPIC_API_KEY")
DATABASE_ONLY = ("DATABASE_URL",)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None
    anthropic_api_key: SecretStr | None = None
    # LLM_* rather than CLAUDE_*: Claude Code exports CLAUDE_* variables of its own,
    # which would silently override these in any shell it runs in.
    llm_model: str = "claude-opus-5-5"
    # Effort trades answer depth for latency; "low" keeps chat turns inside the 8 s p95 target.
    llm_effort: str = "low"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    current_term: str = "Fall 2026"
    retention_days: int = Field(default=90, ge=1, le=90)  # FR-011: never longer than 90 days
    allowed_widget_origins: str = "http://localhost:5173"

    @property
    def widget_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_widget_origins.split(",") if o.strip()]


@lru_cache
def get_settings(require: tuple[str, ...] = REQUIRED) -> Settings:
    """Load settings once, failing fast with a readable message if anything is wrong.

    `require` names the settings the caller cannot run without.
    """
    problems = []
    try:
        settings = Settings()
    except ValidationError as exc:
        settings = None
        for err in exc.errors():
            name = str(err["loc"][0]).upper() if err["loc"] else "?"
            problems.append(f"{name}: {err['msg']}")
    if settings is not None:
        for name in require:
            value = getattr(settings, name.lower())
            if value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"{name} is required but not set")
    if problems:
        raise ConfigError(
            "Invalid configuration (set these in backend/.env; see backend/.env.example):\n  - "
            + "\n  - ".join(problems)
        )
    return settings
