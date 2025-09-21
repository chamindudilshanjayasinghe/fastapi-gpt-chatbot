# FastAPI GPT Chatbot – Step‑by‑Step Starter (Mini ChatGPT)

Build a production‑style ChatGPT‑like backend using **FastAPI + OpenAI + SQLAlchemy (SQLite)** that saves conversations and messages. This guide gives you the *exact* folder structure, files, and commands.

---

## What you’ll build

* `POST /chat` → sends a user message, calls GPT, stores both messages, returns reply
* `GET /conversations` → list conversations (optionally by user)
* `GET /conversations/{id}/messages` → list messages in a conversation

### Why these choices

* **FastAPI** – modern, async‑ready, auto docs at `/docs`
* **SQLAlchemy** – robust ORM for SQLite now, PostgreSQL later
* **OpenAI Chat API** – reliable GPT responses (`gpt-4o-mini` suggested)
* **SQLite** – zero‑config dev DB; swap to Postgres by changing `DATABASE_URL`

---

## 0) Prerequisites

* Python **3.11+**
* An **OpenAI API key**
* Terminal + `pip`

---

## 1) Project structure

```text
fastapi-gpt-chatbot/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ database.py
│  ├─ models.py
│  ├─ schemas.py
│  ├─ openai_client.py
│  ├─ routers/
│  │  ├─ __init__.py
│  │  ├─ chat.py
│  │  └─ conversations.py
│  └─ utils.py
├─ .env.example
├─ requirements.txt
├─ README.md
└─ Dockerfile (optional)
```

---

## 2) Create & install dependencies

**requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
SQLAlchemy==2.0.35
pydantic==2.9.2
openai==1.50.2
python-dotenv==1.0.1
```

Commands

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3) Environment variables

**.env.example**

```env
OPENAI_API_KEY=sk-xxxx
# SQLite local dev (file in project root)
DATABASE_URL=sqlite:///./chat.db
# Example Postgres URL (use later in prod)
# DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
```

> Copy `.env.example` → `.env` and fill your real key.

---

## 4) Database & ORM

**app/database.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# Dependency for FastAPI routes
from typing import Generator

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**app/models.py**

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, func
from .database import Base

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String)  # "system" | "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
```

**Why**: A separate `Conversation` entity lets you group `Message`s and fetch history per thread.

---

## 5) Pydantic schemas

**app/schemas.py**

```python
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
```

**Why**: Pydantic enforces clean request/response contracts and generates docs.

---

## 6) OpenAI client wrapper

**app/openai\_client.py**

```python
import os
from openai import OpenAI

_client: OpenAI | None = None

def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client
```

**Why**: Single place to manage the client and model choice.

---

## 7) Routers

**app/routers/chat.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
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
    db.add(models.Message(conversation_id=conv.id, role="user", content=payload.message))

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
```

**app/routers/conversations.py**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas

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
```

**Why**: Split routers keep code modular and scalable.

---

## 8) FastAPI app entry

**app/main.py**

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from .database import Base, engine
from .routers import chat, conversations

load_dotenv()  # load .env in dev

# Create tables on startup (simple dev approach; Alembic for prod)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FastAPI GPT Chatbot")

# CORS (allow local dev frontends)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(conversations.router)

@app.get("/")
def root():
    return {"ok": True, "service": "fastapi-gpt-chatbot"}
```

**Why**: `create_all` is fine for dev; later switch to Alembic migrations.

---

## 9) Run locally

```bash
uvicorn app.main:app --reload
```

* Browse docs at: **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 10) Try the API

**Start a new conversation**

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"chamindu","message":"Hej! Explain Swedish fika in one sentence."}'
```

Response

```json
{"conversation_id": 1, "reply": "Fika is a Swedish coffee break..."}
```

**Continue the same conversation**

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"chamindu","conversation_id":1,"message":"Give me two pastry examples."}'
```

**List conversations**

```bash
curl 'http://localhost:8000/conversations?user_id=chamindu'
```

**List messages in a conversation**

```bash
curl 'http://localhost:8000/conversations/1/messages'
```

---

## 11) Optional upgrades (nice on GitHub CV)

* **JWT auth**: add `login` endpoint, protect routes with `Depends(get_current_user)`
* **Rate limiting**: integrate `slowapi` to prevent abuse
* **Streaming responses**: use Server‑Sent Events or websockets
* **PostgreSQL**: swap `DATABASE_URL` and add Alembic migrations
* **Docker**: add the following Dockerfile

**Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Why**: These reflect real production concerns recruiters look for.

---

## 12) README.md template (put in repo root)

````md
# FastAPI GPT Chatbot (Mini ChatGPT)

Backend API that stores conversations and calls OpenAI GPT to reply.

## Stack
- FastAPI, SQLAlchemy, SQLite (dev)
- OpenAI Chat Completions API

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your OPENAI_API_KEY
uvicorn app.main:app --reload
````

## Endpoints

* `POST /chat` – send a message and get GPT reply
* `GET /conversations` – list conversations (filter by `user_id`)
* `GET /conversations/{id}/messages` – list messages

Open API docs at [http://localhost:8000/docs](http://localhost:8000/docs)

```

---

## 13) What to commit to GitHub
- All `app/` code
- `requirements.txt`, `README.md`, `.env.example`
- Optional: `Dockerfile`

> **Don’t commit** your real `.env`.

---

## 14) Next steps for you
1. Copy these files into a folder.
2. Add your `OPENAI_API_KEY` in `.env`.
3. Run the server and test the endpoints.
4. Push to GitHub with a clean README and screenshots of `/docs`.
5. Later, add JWT, Postgres, and Docker to impress recruiters.

Good luck — this is a perfect portfolio project! 🚀

```
