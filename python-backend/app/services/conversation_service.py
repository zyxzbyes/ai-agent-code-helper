from datetime import datetime, timezone
import random

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, User


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _conversation_to_dict(conversation: Conversation) -> dict:
    created_at = conversation.created_at
    updated_at = conversation.updated_at or created_at
    return {
        "id": conversation.id,
        "title": conversation.title,
        "memoryId": conversation.memory_id,
        "createdAt": _to_utc_iso(created_at),
        "updatedAt": _to_utc_iso(updated_at),
    }


def _message_to_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "createdAt": _to_utc_iso(message.created_at),
    }


def _generate_memory_id(db: Session) -> int:
    while True:
        memory_id = random.randint(100000000, 999999999)
        exists = db.query(Conversation.id).filter(Conversation.memory_id == memory_id).first()
        if not exists:
            return memory_id


def list_conversations(db: Session, user: User) -> list[dict]:
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .all()
    )
    return [_conversation_to_dict(conversation) for conversation in conversations]


def create_conversation(db: Session, user: User, title: str = "新对话") -> dict:
    safe_title = title.strip() or "新对话"
    conversation = Conversation(
        user_id=user.id,
        title=safe_title[:100],
        memory_id=_generate_memory_id(db),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _conversation_to_dict(conversation)


def get_owned_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return conversation


def list_messages(db: Session, user: User, conversation_id: int) -> list[dict]:
    conversation = get_owned_conversation(db, user, conversation_id)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    return [_message_to_dict(message) for message in messages]


def get_recent_messages(db: Session, conversation: Conversation, limit: int) -> list[Message]:
    if limit <= 0:
        return []

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


def add_message(db: Session, conversation: Conversation, role: str, content: str) -> Message:
    if role not in {"user", "assistant"}:
        raise ValueError("role must be user or assistant")

    message = Message(conversation_id=conversation.id, role=role, content=content)
    conversation.updated_at = _utc_now()
    db.add(message)
    db.add(conversation)
    db.commit()
    db.refresh(message)
    db.refresh(conversation)
    return message


def finalize_chat_messages(
    db: Session,
    conversation: Conversation,
    user_message: str,
    assistant_message: str,
) -> None:
    if conversation.title == "新对话":
        title = user_message.strip().replace("\n", " ")[:20] or "新对话"
        conversation.title = title

    db.add(Message(conversation_id=conversation.id, role="user", content=user_message))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=assistant_message))
    conversation.updated_at = _utc_now()
    db.add(conversation)
    db.commit()


def delete_conversation(db: Session, user: User, conversation_id: int) -> None:
    conversation = get_owned_conversation(db, user, conversation_id)
    db.delete(conversation)
    db.commit()
