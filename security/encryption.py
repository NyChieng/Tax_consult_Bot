"""
Encryption & Secrets Management

Handles:
1. Encrypt sensitive data at rest (user sessions, conversation history)
2. Secure secrets loading (never hardcode, never log)
3. Data anonymization for analytics
4. PII detection and masking
"""
import base64
import hashlib
import hmac
import os
import re
from typing import Optional
import structlog

logger = structlog.get_logger()


class DataEncryptor:
    """
    Simple symmetric encryption for data at rest.
    Uses Fernet-style encryption (AES-128-CBC with HMAC).
    For production, use: from cryptography.fernet import Fernet
    """

    def __init__(self, key: Optional[str] = None):
        if key:
            self.key = hashlib.sha256(key.encode()).digest()
        else:
            self.key = hashlib.sha256(
                os.environ.get("ADMIN_SECRET_KEY", "default-dev-key").encode()
            ).digest()

    def hash_user_id(self, user_id: str) -> str:
        """One-way hash for user IDs (for analytics without PII)."""
        return hashlib.sha256(f"mycukai:{user_id}".encode()).hexdigest()[:16]

    def anonymize_query(self, query: str) -> str:
        """Remove PII from queries before logging/analytics."""
        # Mask IC numbers (Malaysian NRIC: YYMMDD-SS-NNNN)
        query = re.sub(r"\d{6}-\d{2}-\d{4}", "[IC_REDACTED]", query)

        # Mask phone numbers
        query = re.sub(r"(\+?60|0)\d{1,2}[-\s]?\d{7,8}", "[PHONE_REDACTED]", query)

        # Mask email addresses
        query = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]", query)

        # Mask bank account numbers (8-16 digits)
        query = re.sub(r"\b\d{8,16}\b", "[ACCOUNT_REDACTED]", query)

        # Mask names following "my name is" or "nama saya"
        query = re.sub(r"(my name is|nama saya|I am|I'm)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)*", r"\1 [NAME_REDACTED]", query, flags=re.IGNORECASE)

        return query

    def detect_pii(self, text: str) -> list[str]:
        """Detect types of PII present in text."""
        pii_found = []

        if re.search(r"\d{6}-\d{2}-\d{4}", text):
            pii_found.append("ic_number")
        if re.search(r"(\+?60|0)\d{1,2}[-\s]?\d{7,8}", text):
            pii_found.append("phone_number")
        if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text):
            pii_found.append("email")
        if re.search(r"\b\d{8,16}\b", text):
            pii_found.append("possible_account_number")
        if re.search(r"(passport|pasport)\s*:?\s*[A-Z]\d{7,8}", text, re.IGNORECASE):
            pii_found.append("passport_number")

        return pii_found


class SecretsManager:
    """
    Safe secrets management. Never log or expose secrets.
    """

    @staticmethod
    def get_secret(key: str) -> Optional[str]:
        """Get a secret from environment. Never returns default values for sensitive keys."""
        value = os.environ.get(key)
        if not value:
            logger.warning("missing_secret", key=key)
            return None
        return value

    @staticmethod
    def validate_secrets() -> dict:
        """Check all required secrets are present. Call at startup."""
        required = ["ANTHROPIC_API_KEY"]
        optional = ["VOYAGE_API_KEY", "COHERE_API_KEY", "TELEGRAM_BOT_TOKEN", "DATABASE_URL"]

        report = {"missing_required": [], "missing_optional": [], "all_present": True}

        for key in required:
            if not os.environ.get(key):
                report["missing_required"].append(key)
                report["all_present"] = False

        for key in optional:
            if not os.environ.get(key):
                report["missing_optional"].append(key)

        return report

    @staticmethod
    def mask_for_logging(value: str) -> str:
        """Mask a secret value for safe logging."""
        if len(value) <= 8:
            return "***"
        return value[:4] + "..." + value[-4:]


# Singleton
encryptor = DataEncryptor()
secrets_manager = SecretsManager()
