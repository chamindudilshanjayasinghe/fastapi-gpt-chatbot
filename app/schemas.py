from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class ChatRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    conversation_id: Optional[int] = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str


class ConversationOut(BaseModel):
    id: int
    user_id: Optional[str]
    title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageList(BaseModel):
    conversation_id: int
    messages: List[MessageOut]
