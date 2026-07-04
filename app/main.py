from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.chat import register_validation_logger, router as chat_router
from app.routes.xero_auth import router as xero_auth_router

settings = get_settings()

app = FastAPI(
    title="Voca",
    description="Xero without ever opening Xero — voice-first setup & operation agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_validation_logger(app)
app.include_router(chat_router)
app.include_router(xero_auth_router)


@app.get("/")
def root() -> dict:
    return {
        "name": "voca",
        "tagline": "Xero without ever opening Xero",
        "status": "scaffold",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "chat": "/api/chat",
            "xero_connect": "/auth/xero?session_id=...",
            "xero_status": "/auth/xero/status?session_id=...",
            "voice_webhook": "/voice/webhook",
        },
    }


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "environment": settings.environment,
        "xero_app_configured": settings.xero_app_configured,
        "ai_configured": settings.ai_configured,
        "model": settings.ai_default_model,
    }


@app.post("/voice/webhook")
async def voice_webhook() -> dict:
    # ElevenLabs conversational AI → forwards to /api/chat (Day 1 PM)
    return {"error": "Not implemented yet — wire ElevenLabs to /api/chat"}
