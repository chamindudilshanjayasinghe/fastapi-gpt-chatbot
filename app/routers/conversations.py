from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[schemas.ConversationOut])
def list_conversations(
    user_id: str | None = Query(None, description="Filter by user_id"),
    db: Session = Depends(get_db),
):
    q = db.query(models.Conversation)
    if user_id:
        q = q.filter(models.Conversation.user_id == user_id)
    return q.order_by(models.Conversation.created_at.desc()).all()


@router.get("/{conversation_id}/messages", response_model=schemas.MessageList)
def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(models.Conversation, conversation_id)
    if not conv:
        return {"conversation_id": conversation_id, "messages": []}

    msgs = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )

    return {
        "conversation_id": conversation_id,
        "messages": msgs,
    }
