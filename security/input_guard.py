"""
Input Guard - Prevents prompt injection, XSS, SQL injection, and abuse.

Threat Model:
1. PROMPT INJECTION: Attacker tries to override system prompt
2. DATA EXFILTRATION: Attacker tries to make bot reveal system prompt or API keys
3. XSS/HTML INJECTION: Attacker injects malicious HTML/JS through bot responses
4. SQL INJECTION: Attacker targets any database queries
5. RESOURCE ABUSE: Attacker sends extremely long messages or rapid-fire requests
6. SOCIAL ENGINEERING: Attacker pretends to be admin / developer
7. JAILBREAK: Attacker tries to make bot give illegal tax evasion advice
"""
import re
import hashlib
from typing import Optional
import structlog

logger = structlog.get_logger()

# Max input length (tokens are roughly 4 chars each, 512 tokens = ~2048 chars)
MAX_INPUT_LENGTH = 2000
MIN_INPUT_LENGTH = 2

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    # Direct instruction overrides
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)",
    r"disregard\s+(your|all|the)\s+(instructions|rules|guidelines)",
    r"forget\s+(everything|all|your)\s+(above|previous|instructions)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"new\s+(instructions|prompt|role|persona)",
    r"system\s*:\s*",
    r"###\s*(system|instruction|prompt)",
    r"\[SYSTEM\]",
    r"<\s*system\s*>",

    # Data exfiltration attempts
    r"(show|tell|reveal|display|print|output)\s+(me\s+)?(your|the)\s+(system\s+prompt|instructions|api\s*key|secret|password)",
    r"what\s+(is|are)\s+your\s+(system\s+prompt|instructions|rules)",
    r"repeat\s+(your|the)\s+(system|initial)\s+(prompt|instructions|message)",
    r"(dump|leak|expose)\s+(your|the|all)\s+(data|prompt|config)",

    # Role-play manipulation
    r"pretend\s+(you\s+are|to\s+be)\s+(a|an)\s+",
    r"act\s+as\s+(if|though)\s+you",
    r"roleplay\s+as",
    r"you\s+are\s+DAN",
    r"jailbreak",

    # Attempting to bypass tax advice restrictions
    r"(help|tell)\s+me\s+(how\s+to\s+)?(evade|avoid|escape|cheat)\s+(tax|LHDN|cukai)",
    r"(hide|conceal)\s+(income|money|earnings)\s+from\s+(LHDN|tax|government)",
    r"(illegal|illicit)\s+(tax|income)\s+(scheme|strategy)",
]

# Patterns for XSS/HTML injection
XSS_PATTERNS = [
    r"<script[^>]*>",
    r"javascript\s*:",
    r"on(load|error|click|mouseover)\s*=",
    r"<iframe",
    r"<object",
    r"<embed",
    r"<form[^>]*action",
    r"document\.(cookie|location|write)",
    r"window\.(location|open)",
    r"eval\s*\(",
    r"<img[^>]*onerror",
]

# SQL injection patterns
SQL_PATTERNS = [
    r";\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)\s+",
    r"'\s*(OR|AND)\s+'?\d+'?\s*=\s*'?\d+",
    r"UNION\s+(ALL\s+)?SELECT",
    r"--\s*$",
    r"/\*.*\*/",
    r"xp_cmdshell",
    r"exec\s*\(",
]

# Compile patterns for performance
_injection_re = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_xss_re = [re.compile(p, re.IGNORECASE) for p in XSS_PATTERNS]
_sql_re = [re.compile(p, re.IGNORECASE) for p in SQL_PATTERNS]


class InputGuard:
    def __init__(self):
        self.blocked_count = 0
        self.suspicious_users: dict[str, int] = {}

    def validate(self, user_input: str, user_id: str = "anonymous") -> dict:
        """
        Validate user input. Returns:
        {
            "safe": bool,
            "sanitized": str,  # cleaned input
            "threat_type": str | None,
            "threat_level": "none" | "low" | "medium" | "high" | "critical"
        }
        """
        # Length check
        if len(user_input) < MIN_INPUT_LENGTH:
            return {"safe": True, "sanitized": user_input, "threat_type": None, "threat_level": "none"}

        if len(user_input) > MAX_INPUT_LENGTH:
            return {
                "safe": False,
                "sanitized": user_input[:MAX_INPUT_LENGTH],
                "threat_type": "input_too_long",
                "threat_level": "low",
            }

        # Prompt injection check
        injection = self._check_injection(user_input)
        if injection:
            self._record_suspicious(user_id, "prompt_injection")
            logger.warning("prompt_injection_blocked", user_id=user_id, pattern=injection)
            return {
                "safe": False,
                "sanitized": "",
                "threat_type": "prompt_injection",
                "threat_level": "high",
            }

        # XSS check
        xss = self._check_xss(user_input)
        if xss:
            self._record_suspicious(user_id, "xss_attempt")
            logger.warning("xss_blocked", user_id=user_id)
            return {
                "safe": False,
                "sanitized": self._strip_html(user_input),
                "threat_type": "xss_attempt",
                "threat_level": "medium",
            }

        # SQL injection check
        sql = self._check_sql_injection(user_input)
        if sql:
            self._record_suspicious(user_id, "sql_injection")
            logger.warning("sql_injection_blocked", user_id=user_id)
            return {
                "safe": False,
                "sanitized": "",
                "threat_type": "sql_injection",
                "threat_level": "critical",
            }

        # Tax evasion advice check
        if self._check_illegal_request(user_input):
            return {
                "safe": False,
                "sanitized": user_input,
                "threat_type": "illegal_advice_request",
                "threat_level": "medium",
            }

        # Check if user is on suspicious list (too many attempts)
        if self._is_banned(user_id):
            return {
                "safe": False,
                "sanitized": "",
                "threat_type": "user_banned",
                "threat_level": "critical",
            }

        # Sanitize (remove control characters, normalize)
        sanitized = self._sanitize(user_input)

        return {"safe": True, "sanitized": sanitized, "threat_type": None, "threat_level": "none"}

    def _check_injection(self, text: str) -> Optional[str]:
        for pattern in _injection_re:
            if pattern.search(text):
                return pattern.pattern
        return None

    def _check_xss(self, text: str) -> Optional[str]:
        for pattern in _xss_re:
            if pattern.search(text):
                return pattern.pattern
        return None

    def _check_sql_injection(self, text: str) -> Optional[str]:
        for pattern in _sql_re:
            if pattern.search(text):
                return pattern.pattern
        return None

    def _check_illegal_request(self, text: str) -> bool:
        illegal_patterns = [
            r"(evade|avoid paying|cheat|hide from)\s*(tax|LHDN|cukai)",
            r"(money laundering|launder|haram money)",
            r"(fake|forge|fabricate)\s*(receipt|invoice|document)",
        ]
        for p in illegal_patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    def _sanitize(self, text: str) -> str:
        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Remove zero-width characters (used in steganographic attacks)
        text = re.sub(r"[​-‏ - ⁠-⁯﻿]", "", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _strip_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)

    def _record_suspicious(self, user_id: str, threat_type: str):
        key = user_id
        self.suspicious_users[key] = self.suspicious_users.get(key, 0) + 1
        self.blocked_count += 1

    def _is_banned(self, user_id: str) -> bool:
        # Ban after 5 suspicious attempts
        return self.suspicious_users.get(user_id, 0) >= 5


# Singleton
input_guard = InputGuard()
