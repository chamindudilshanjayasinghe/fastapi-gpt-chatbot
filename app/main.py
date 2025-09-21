from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
