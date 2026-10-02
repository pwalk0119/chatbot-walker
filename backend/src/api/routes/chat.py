"""Chat routes. POST /api/chat/conversations (T021); the messages route arrives in T036."""

from fastapi import APIRouter, status

from src.api.deps import Connect
from src.api.schemas import ConversationOut
from src.db.repositories import conversations

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationOut,
    operation_id="startConversation",
)
def start_conversation(connect: Connect) -> ConversationOut:
    with connect() as conn:
        convo = conversations.create_conversation(conn)
    return ConversationOut(
        id=convo.id,
        campus=convo.campus,
        academic_level=convo.academic_level,
        status=convo.status,
    )
