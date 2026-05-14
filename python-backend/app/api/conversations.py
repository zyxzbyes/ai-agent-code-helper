from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.common import success_response
from app.schemas.conversation_schema import ConversationCreate
from app.services import conversation_service


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        data=conversation_service.list_conversations(db, current_user),
        message="success",
    )


@router.post("")
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = conversation_service.create_conversation(db, current_user, payload.title)
    return success_response(data=conversation, message="success")


@router.get("/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(
        data=conversation_service.list_messages(db, current_user, conversation_id),
        message="success",
    )


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation_service.delete_conversation(db, current_user, conversation_id)
    return success_response(data=True, message="success")
