import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped["datetime"] = mapped_column(  # type: ignore
        DateTime(timezone=True), server_default=func.now()
    )

    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped["datetime"] = mapped_column(  # type: ignore
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
