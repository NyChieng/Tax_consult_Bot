from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
import redis.asyncio as redis
import structlog

from config import settings
from bot.conversation import handle_query
from security.audit_log import audit_log
from security.encryption import secrets_manager

logger = structlog.get_logger()

redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client

    # Validate secrets at startup
    secrets_report = secrets_manager.validate_secrets()
    if not secrets_report["all_present"]:
        logger.warning("missing_secrets", missing=secrets_report["missing_required"])

    try:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("redis_connected")
    except Exception as e:
        logger.warning("redis_unavailable", error=str(e))
        redis_client = None

    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn)

    audit_log.log("system_startup", details={"environment": settings.environment})
    yield

    if redis_client:
        await redis_client.close()
    audit_log.log("system_shutdown")


app = FastAPI(
    title="MyCukai Tax Assistant API",
    version="1.0.0",
    description="Malaysian Tax Reference Bot powered by RAG + Claude",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

# Security: Only allow specific origins in production
allowed_origins = ["*"] if settings.environment == "development" else [
    "https://mycukai.my",
    "https://www.mycukai.my",
    "https://app.mycukai.my",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Api-Key", "X-Admin-Key", "Content-Type"],
)

# Security: Trusted host middleware (prevent host header attacks)
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["mycukai.my", "*.mycukai.my", "*.onrender.com"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response: Response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

    # Remove server identification
    response.headers.pop("server", None)

    return response


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field(default="anonymous", max_length=100)
    conversation_history: list[dict] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    response: str
    intent: str
    language: str
    sources: list[str]


class FeedbackRequest(BaseModel):
    interaction_id: str = Field(..., min_length=1, max_length=20)
    score: float = Field(..., ge=0.0, le=1.0)
    feedback_type: str = Field(..., pattern="^(thumbs_up|thumbs_down|correction)$")
    correction: str = Field(default="", max_length=500)


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/freshness")
async def freshness():
    return {
        "last_scrape": "check_database",
        "total_documents": "check_vector_store",
        "status": "operational",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, raw_request: Request):
    ip_address = raw_request.client.host if raw_request.client else ""

    # All security checks (rate limiting, input validation, etc.) are now
    # handled inside handle_query with the integrated security layer
    result = await handle_query(
        user_message=request.message,
        conversation_history=request.conversation_history,
        user_id=request.user_id,
        ip_address=ip_address,
    )

    if result.get("blocked"):
        raise HTTPException(
            status_code=429 if result["intent"] == "rate_limited" else 400,
            detail=result["response"],
        )

    return ChatResponse(
        response=result["response"],
        intent=result["intent"],
        language=result["language"],
        sources=result["sources"],
    )


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Allow users to rate responses — feeds the self-learning system."""
    from agent.learning.feedback_loop import FeedbackLoop
    feedback = FeedbackLoop()
    feedback.record_feedback(
        interaction_id=request.interaction_id,
        score=request.score,
        feedback_type=request.feedback_type,
        user_correction=request.correction if request.correction else None,
    )
    return {"status": "feedback_recorded"}


@app.post("/admin/trigger-update")
async def trigger_update(raw_request: Request):
    auth = raw_request.headers.get("X-Admin-Key")
    if not auth or auth != settings.admin_secret_key:
        audit_log.log("auth_failure", details={"endpoint": "/admin/trigger-update"}, severity="warning")
        raise HTTPException(status_code=403, detail="Unauthorized")

    audit_log.log("admin_action", details={"action": "trigger_update"})

    from scraper.lhdn_spider import run as run_lhdn
    from processor.pipeline import process_all
    from embedder.vector_store import embed_all_chunks

    run_lhdn()
    process_all()
    embed_all_chunks()

    return {"status": "update_triggered", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/admin/security-report")
async def security_report(raw_request: Request):
    """Admin-only: view security events and anomalies."""
    auth = raw_request.headers.get("X-Admin-Key")
    if not auth or auth != settings.admin_secret_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    recent_events = audit_log.get_recent_events(50)
    anomalies = audit_log.detect_anomalies()
    integrity = audit_log.verify_integrity()

    return {
        "recent_events": recent_events[-10:],
        "anomalies": anomalies,
        "log_integrity": integrity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/admin/learning-status")
async def learning_status(raw_request: Request):
    """Admin-only: view self-learning system status."""
    auth = raw_request.headers.get("X-Admin-Key")
    if not auth or auth != settings.admin_secret_key:
        raise HTTPException(status_code=403, detail="Unauthorized")

    from agent.learning.feedback_loop import FeedbackLoop
    from agent.learning.memory_store import MemoryStore

    feedback = FeedbackLoop()
    memory = MemoryStore()

    return {
        "unresolved_gaps": len(feedback.get_unresolved_gaps()),
        "meta_knowledge": memory.meta,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
