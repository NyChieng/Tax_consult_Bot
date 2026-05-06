"""
Authentication and Authorization Layer

Handles:
1. API key authentication for external consumers
2. Admin authentication for management endpoints
3. JWT tokens for web widget sessions
4. Telegram user verification
5. Webhook signature validation
"""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException, Request, Header
import structlog

from config import settings

logger = structlog.get_logger()

# In production, store these in database
API_KEYS_STORE: dict[str, dict] = {}


def generate_api_key(tier: str = "free", user_id: str = "") -> dict:
    """Generate a new API key for a consumer."""
    key = f"mk_{tier}_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    record = {
        "key_hash": key_hash,
        "tier": tier,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None,
        "requests_today": 0,
        "is_active": True,
    }

    API_KEYS_STORE[key_hash] = record
    return {"api_key": key, "tier": tier}


def validate_api_key(api_key: str) -> Optional[dict]:
    """Validate an API key and return associated metadata."""
    if not api_key or not api_key.startswith("mk_"):
        return None

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    record = API_KEYS_STORE.get(key_hash)

    if not record:
        return None

    if not record["is_active"]:
        return None

    # Update usage
    record["last_used"] = datetime.now(timezone.utc).isoformat()
    record["requests_today"] += 1

    return record


def verify_admin(admin_key: str) -> bool:
    """Verify admin access."""
    if not admin_key:
        return False
    return hmac.compare_digest(admin_key, settings.admin_secret_key)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature (for Telegram, Stripe, etc.)."""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_session_token(user_id: str, expires_hours: int = 24) -> str:
    """Create a simple session token for web widget."""
    expiry = int(time.time()) + (expires_hours * 3600)
    data = f"{user_id}:{expiry}"
    signature = hmac.new(
        settings.admin_secret_key.encode(),
        data.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"{data}:{signature}"


def validate_session_token(token: str) -> Optional[str]:
    """Validate session token, returns user_id if valid."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None

        user_id, expiry_str, signature = parts
        expiry = int(expiry_str)

        if time.time() > expiry:
            return None

        data = f"{user_id}:{expiry_str}"
        expected_sig = hmac.new(
            settings.admin_secret_key.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        if hmac.compare_digest(signature, expected_sig):
            return user_id
        return None

    except (ValueError, IndexError):
        return None


# FastAPI dependency for protected routes
async def require_admin(x_admin_key: str = Header(None)):
    if not verify_admin(x_admin_key or ""):
        raise HTTPException(status_code=403, detail="Invalid admin credentials")
    return True


async def require_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    record = validate_api_key(x_api_key)
    if not record:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return record
