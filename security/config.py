"""
Security Configuration - Central place for all security settings.

OWASP Top 10 Compliance Checklist:
[x] A01:2021 - Broken Access Control → auth.py + admin key validation
[x] A02:2021 - Cryptographic Failures → encryption.py + no hardcoded secrets
[x] A03:2021 - Injection → input_guard.py (SQL, XSS, prompt injection)
[x] A04:2021 - Insecure Design → rate_limiter.py + least privilege (Dockerfile USER)
[x] A05:2021 - Security Misconfiguration → security headers + .dockerignore
[x] A06:2021 - Vulnerable Components → requirements pinned + no dev deps in prod
[x] A07:2021 - Auth Failures → rate limiting on auth + audit logging
[x] A08:2021 - Data Integrity Failures → chained hash audit log
[x] A09:2021 - Logging & Monitoring → audit_log.py + anomaly detection
[x] A10:2021 - SSRF → no user-controlled URLs in backend requests
"""

# Maximum message size (characters)
MAX_MESSAGE_LENGTH = 2000

# Rate limiting
RATE_LIMIT_PER_HOUR = 30
RATE_LIMIT_PER_MINUTE = 10
BURST_THRESHOLD = 5
BURST_WINDOW_SECONDS = 10
BAN_DURATION_SECONDS = 300

# Session management
SESSION_TTL_SECONDS = 86400  # 24 hours
MAX_SESSION_HISTORY = 20

# Input validation
BLOCKED_RESPONSE_CODES = {
    "prompt_injection": 400,
    "xss_attempt": 400,
    "sql_injection": 400,
    "illegal_advice_request": 400,
    "user_banned": 403,
    "rate_limited": 429,
}

# Output filtering
MAX_RESPONSE_LENGTH = 10000
ALWAYS_REQUIRE_DISCLAIMER = True

# Audit
AUDIT_RETENTION_DAYS = 90
ALERT_ON_CRITICAL = True

# Self-learning safety
MAX_GOLDEN_EXAMPLES = 1000
MAX_KNOWLEDGE_GAPS = 500
SELF_CRITIQUE_SAMPLE_RATE = 0.10  # 10% of queries
AUTO_BAN_AFTER_INJECTIONS = 5
