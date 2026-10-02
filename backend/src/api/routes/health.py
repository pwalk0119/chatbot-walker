"""GET /api/chat/health (T018)."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.deps import LLM, Connect

router = APIRouter(prefix="/api/chat", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health(connect: Connect, llm: LLM) -> JSONResponse:
    """200 only when the vector store is reachable and the Claude client is configured."""
    checks: dict[str, str] = {}

    try:
        with connect() as conn:
            conn.execute("SELECT 1")
            has_vector = conn.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
        checks["database"] = "ok" if has_vector else "missing pgvector extension"
    except Exception as exc:  # any connection failure means "not ready"
        logger.warning("health: database check failed: %s", exc)
        checks["database"] = "unreachable"

    # Configured = a client was built from settings. No API call, so the probe stays free.
    checks["llm"] = "configured" if llm is not None else "not configured"

    healthy = checks["database"] == "ok" and checks["llm"] == "configured"
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "unavailable", **checks},
    )
