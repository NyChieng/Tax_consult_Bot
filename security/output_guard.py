"""
Output Guard - Prevents the bot from leaking sensitive data in responses.

Protects against:
1. System prompt leakage (bot accidentally revealing its instructions)
2. API key / credential leakage
3. Internal path disclosure
4. PII leakage (user data from one session appearing in another)
5. Harmful content (tax evasion advice slipping through)
"""
import re
from typing import Optional
import structlog

logger = structlog.get_logger()

# Patterns that should NEVER appear in bot output
SENSITIVE_PATTERNS = [
    # API keys and credentials
    (r"sk-ant-[a-zA-Z0-9\-_]{20,}", "anthropic_key"),
    (r"pa-[a-zA-Z0-9\-_]{20,}", "voyage_key"),
    (r"[a-zA-Z0-9]{32,40}", "possible_api_key"),
    (r"Bearer\s+[a-zA-Z0-9\-_.]{20,}", "bearer_token"),

    # Database credentials
    (r"postgresql://[^\s]+", "database_url"),
    (r"redis://[^\s]+", "redis_url"),
    (r"password[\"']?\s*[:=]\s*[\"'][^\"']+[\"']", "password_leak"),

    # Internal paths
    (r"[A-Z]:\\Users\\[^\s]+", "windows_path"),
    (r"/home/[a-zA-Z0-9_]+/", "linux_home_path"),
    (r"/app/[a-zA-Z0-9_/]+\.py", "internal_code_path"),

    # System prompt markers
    (r"SYSTEM PROMPT|system_prompt|SystemPrompt", "system_prompt_leak"),
    (r"MY INSTRUCTIONS ARE|MY RULES ARE", "instruction_leak"),
]

# Content that indicates harmful advice
HARMFUL_OUTPUT_PATTERNS = [
    r"here('s| is)\s+how\s+to\s+(evade|avoid paying|cheat on)\s+tax",
    r"you\s+can\s+hide\s+(income|money)\s+by",
    r"(don't|do not)\s+report\s+(this|your)\s+(income|earnings)",
    r"LHDN\s+(won't|will not)\s+(find out|know|discover)",
    r"fake\s+(receipt|invoice|document)\s+to\s+claim",
]

_sensitive_re = [(re.compile(p, re.IGNORECASE), label) for p, label in SENSITIVE_PATTERNS]
_harmful_re = [re.compile(p, re.IGNORECASE) for p in HARMFUL_OUTPUT_PATTERNS]


class OutputGuard:
    def __init__(self):
        self.leaks_detected = 0

    def sanitize_output(self, response: str) -> dict:
        """
        Check and sanitize bot output before sending to user.
        Returns:
        {
            "safe": bool,
            "response": str,  # cleaned response
            "issues": list[str],
        }
        """
        issues = []

        # Check for sensitive data leakage
        for pattern, label in _sensitive_re:
            if pattern.search(response):
                response = pattern.sub("[REDACTED]", response)
                issues.append(f"redacted_{label}")
                self.leaks_detected += 1
                logger.warning("output_leak_detected", type=label)

        # Check for harmful content
        for pattern in _harmful_re:
            if pattern.search(response):
                issues.append("harmful_content")
                response = self._replace_harmful(response)
                logger.warning("harmful_output_blocked")
                break

        # Ensure disclaimer is present for substantive tax answers
        if len(response) > 200 and "⚠️" not in response and "Disclaimer" not in response:
            issues.append("missing_disclaimer")

        return {
            "safe": len(issues) == 0,
            "response": response,
            "issues": issues,
        }

    def _replace_harmful(self, response: str) -> str:
        """Replace harmful content with appropriate refusal."""
        return (
            "I cannot provide advice on tax evasion or illegal activities. "
            "Tax evasion is a criminal offence under Malaysian law (Section 114 of the Income Tax Act 1967) "
            "and carries penalties including fines and imprisonment.\n\n"
            "If you have concerns about your tax obligations, please consult a registered tax agent "
            "who can help you find LEGAL ways to minimize your tax liability within the law."
        )


# Singleton
output_guard = OutputGuard()
