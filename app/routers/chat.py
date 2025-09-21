from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..openai_client import get_openai_client

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = (
    "You are a helpful, concise assistant. Keep replies short unless asked for detail."
)


@router.post("", response_model=schemas.ChatResponse)
def chat(payload: schemas.ChatRequest, db: Session = Depends(get_db)):
    # 1) Find or create conversation
    if payload.conversation_id is None:
        conv = models.Conversation(user_id=payload.user_id, title=None)
        db.add(conv)
        db.flush()  # get conv.id before commit
    else:
        conv = db.get(models.Conversation, payload.conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # 2) Persist user message
    db.add(
        models.Message(conversation_id=conv.id, role="user", content=payload.message)
    )

    # 3) Build message history (last 20 + system)
    history = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conv.id)
        .order_by(models.Message.created_at.desc())
        .limit(20)
        .all()
    )
    # oldest → newest
    history = list(reversed(history))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        {"role": m.role, "content": m.content} for m in history
    ]

    # 4) Call OpenAI
    client = get_openai_client()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
    )
    reply = completion.choices[0].message.content

    # 5) Save assistant reply
    db.add(models.Message(conversation_id=conv.id, role="assistant", content=reply))
    db.commit()
    db.refresh(conv)

    return schemas.ChatResponse(conversation_id=conv.id, reply=reply)
