from collections.abc import Iterator
import json

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user_from_authorization
from app.db.database import get_db
from app.services import conversation_service
from app.services.chat_service import chat_service


router = APIRouter(prefix="/api/ai", tags=["ai"])


def _format_sse(data: str) -> str:
    normalized = str(data).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(f"data: {line}\n" for line in normalized.split("\n")) + "\n"


def _format_sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    lines = [f"event: {event}"]
    lines.extend(f"data: {line}" for line in normalized.split("\n"))
    return "\n".join(lines) + "\n\n"


@router.get("/chat")
def chat(
    conversationId: int | None = Query(None, description="Persistent conversation id."),
    memoryId: int | None = Query(None, description="Chat memory id, compatible with the Java API."),
    message: str = Query("", description="User message."),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    current_user = None
    if conversationId is not None:
        current_user = get_current_user_from_authorization(db=db, authorization=authorization)
        conversation_service.get_owned_conversation(db, current_user, conversationId)

    def event_stream() -> Iterator[str]:
        if not message or not message.strip():
            yield _format_sse("错误：message 不能为空")
            yield _format_sse("[DONE]")
            return

        if conversationId is not None and current_user is not None:
            chunks = chat_service.stream_conversation_chat(
                db=db,
                user=current_user,
                conversation_id=conversationId,
                message=message,
            )
        else:
            if memoryId is None:
                yield _format_sse("错误：conversationId 或 memoryId 不能为空")
                yield _format_sse("[DONE]")
                return
            chunks = chat_service.stream_chat(memory_id=memoryId, message=message)

        for chunk in chunks:
            if not chunk:
                continue
            if getattr(chunk, "type", "content") == "sources":
                yield _format_sse_event("sources", {"sources": getattr(chunk, "sources", [])})
                continue
            content = getattr(chunk, "content", chunk)
            if content:
                yield _format_sse(content)

        yield _format_sse("[DONE]")

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=headers,
    )
