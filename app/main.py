import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import db_enabled, init_db
from app.routes.chat import register_validation_logger, router as chat_router
from app.routes.messages import router as messages_router
from app.routes.demo import router as demo_router
from app.routes.xero_auth import router as xero_auth_router

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Voca",
    description="WhatsApp bookkeeper for Xero — text and voice notes via Wassist",
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
app.include_router(messages_router)
app.include_router(demo_router)
app.include_router(xero_auth_router)


@app.on_event("startup")
async def on_startup() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    from app.voice_fast import warm_voice_cache
    from app.wassist import demo_connection_id

    connection_id = demo_connection_id()
    if connection_id:
        asyncio.create_task(warm_voice_cache(connection_id))
        logger.info("warming receivables cache for %s", connection_id[:20])


@app.get("/")
def root() -> dict:
    return {
        "name": "voca",
        "tagline": "Xero without ever opening Xero",
        "status": "scaffold",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "xero_connect": "/auth/xero?session_id=...",
            "xero_status": "/auth/xero/status?session_id=...",
            "demo_mirror": "/demo (Next.js)",
            "demo_state": "/api/demo/state",
            "receipts_upload": "/receipts/upload",
            "whatsapp_byoa": "/whatsapp/byoa",
            "whatsapp_link": "/api/whatsapp/link",
            "whatsapp_webhook": "/whatsapp/webhook (legacy)",
            "whatsapp_receipt": "/whatsapp/receipt",
        },
    }


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "environment": settings.environment,
        "xero_app_configured": settings.xero_app_configured,
        "ai_configured": settings.ai_configured,
        "database_configured": db_enabled(),
        "model": settings.ai_default_model,
        "whatsapp_configured": bool(settings.public_base_url),
        "public_base_url": settings.public_base_url or None,
    }
