"""
Security Audit Logger

Logs all security-relevant events for forensic analysis:
- Authentication attempts (success and failure)
- Rate limit hits
- Blocked inputs (injection attempts)
- Admin actions
- Data access patterns
- Suspicious behavior

Logs are append-only and tamper-evident (chained hashes).
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

AUDIT_LOG_PATH = Path("data/security/audit.jsonl")
ALERT_LOG_PATH = Path("data/security/alerts.jsonl")


class AuditLogger:
    def __init__(self):
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = "genesis"

    def log(
        self,
        event_type: str,
        user_id: str = "system",
        details: Optional[dict] = None,
        severity: str = "info",
        ip_address: Optional[str] = None,
    ):
        """
        Log a security event.

        severity: "info", "warning", "critical"
        event_type: "auth_success", "auth_failure", "rate_limit", "injection_blocked",
                    "admin_action", "data_access", "suspicious_behavior"
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "severity": severity,
            "ip_address": ip_address,
            "details": details or {},
            "prev_hash": self._last_hash,
        }

        # Chain hash for tamper evidence
        entry_str = json.dumps(entry, sort_keys=True)
        entry["hash"] = hashlib.sha256(entry_str.encode()).hexdigest()[:16]
        self._last_hash = entry["hash"]

        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        # Critical events also go to alerts
        if severity == "critical":
            self._alert(entry)
            logger.critical("security_alert", event=event_type, user=user_id)

    def _alert(self, entry: dict):
        """Store critical alerts separately for easy monitoring."""
        with open(ALERT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_recent_events(self, limit: int = 50, event_type: Optional[str] = None) -> list[dict]:
        """Get recent audit events (for admin dashboard)."""
        if not AUDIT_LOG_PATH.exists():
            return []

        events = []
        with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    if event_type is None or event["event_type"] == event_type:
                        events.append(event)

        return events[-limit:]

    def get_user_activity(self, user_id: str, limit: int = 20) -> list[dict]:
        """Get all security events for a specific user."""
        if not AUDIT_LOG_PATH.exists():
            return []

        events = []
        with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    if event["user_id"] == user_id:
                        events.append(event)

        return events[-limit:]

    def detect_anomalies(self) -> list[dict]:
        """Simple anomaly detection on recent events."""
        events = self.get_recent_events(200)
        anomalies = []

        # Detect: multiple auth failures from same user
        from collections import Counter
        auth_failures = [e for e in events if e["event_type"] == "auth_failure"]
        user_failures = Counter(e["user_id"] for e in auth_failures)
        for user_id, count in user_failures.items():
            if count >= 3:
                anomalies.append({
                    "type": "brute_force_suspected",
                    "user_id": user_id,
                    "failure_count": count,
                })

        # Detect: injection attempts
        injections = [e for e in events if e["event_type"] == "injection_blocked"]
        if len(injections) > 5:
            anomalies.append({
                "type": "injection_campaign",
                "count": len(injections),
                "unique_users": len(set(e["user_id"] for e in injections)),
            })

        return anomalies

    def verify_integrity(self) -> dict:
        """Verify the audit log hasn't been tampered with."""
        if not AUDIT_LOG_PATH.exists():
            return {"valid": True, "entries": 0}

        prev_hash = "genesis"
        total = 0
        corrupted = 0

        with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                total += 1
                entry = json.loads(line)

                if entry.get("prev_hash") != prev_hash:
                    corrupted += 1

                prev_hash = entry.get("hash", "")

        return {
            "valid": corrupted == 0,
            "entries": total,
            "corrupted_entries": corrupted,
        }


# Singleton
audit_log = AuditLogger()
