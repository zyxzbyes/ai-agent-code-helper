import logging

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.ai import router as ai_router
from app.api.conversations import router as conversations_router
from app.api.guardrails import router as guardrails_router
from app.api.rag import router as rag_router
from app.api.tools import router as tools_router
from app.core.cors import configure_cors
from app.db.init_db import init_db
from app.schemas.common import success_response


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="AI Code Helper Python Backend",
    description="FastAPI MVP backend compatible with the original Java SSE chat API.",
    version="0.1.0",
)

configure_cors(app)
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(guardrails_router)
app.include_router(rag_router)
app.include_router(tools_router)
app.include_router(ai_router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return success_response(data={"status": "UP"})
