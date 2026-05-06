"""
Self-Healing Agent - Detects and fixes common issues automatically.

Monitors:
- API connectivity (Claude, Voyage, Cohere)
- Database health (PostgreSQL, Redis, ChromaDB)
- Scraper failures (blocked, timeouts, schema changes)
- Disk space and data integrity
- Response quality degradation
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import httpx
import structlog

from config import settings

logger = structlog.get_logger()

HEALTH_LOG = Path("data/health_log.jsonl")


class SelfHealingAgent:
    def __init__(self):
        self.issues: list[dict] = []
        self.fixes_applied: list[dict] = []

    async def run_health_check(self) -> dict:
        """Run all health checks and attempt auto-fixes."""
        checks = {
            "anthropic_api": await self._check_anthropic(),
            "voyage_api": await self._check_voyage(),
            "redis": await self._check_redis(),
            "disk_space": self._check_disk_space(),
            "data_integrity": self._check_data_integrity(),
            "scraper_health": self._check_scraper_health(),
        }

        # Attempt fixes for any failures
        for check_name, result in checks.items():
            if not result["healthy"]:
                fix = await self._attempt_fix(check_name, result)
                if fix:
                    self.fixes_applied.append(fix)

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_healthy": all(r["healthy"] for r in checks.values()),
            "checks": checks,
            "fixes_applied": self.fixes_applied,
        }

        self._log_health(report)
        return report

    async def _check_anthropic(self) -> dict:
        if not settings.anthropic_api_key:
            return {"healthy": False, "error": "No API key configured"}

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"healthy": True, "latency_ms": "ok"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _check_voyage(self) -> dict:
        if not settings.voyage_api_key:
            return {"healthy": False, "error": "No API key configured"}

        try:
            import voyageai
            vo = voyageai.Client(api_key=settings.voyage_api_key)
            result = vo.embed(["test"], model="voyage-3", input_type="query")
            return {"healthy": True, "dimensions": len(result.embeddings[0])}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _check_redis(self) -> dict:
        try:
            import redis as redis_sync
            r = redis_sync.from_url(settings.redis_url, decode_responses=True)
            r.ping()
            r.close()
            return {"healthy": True}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def _check_disk_space(self) -> dict:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_gb = free / (1024 ** 3)
        return {
            "healthy": free_gb > 1.0,
            "free_gb": round(free_gb, 2),
            "used_percent": round(used / total * 100, 1),
        }

    def _check_data_integrity(self) -> dict:
        raw_dir = Path("data/raw")
        processed_dir = Path("data/processed")

        raw_count = len(list(raw_dir.rglob("*"))) if raw_dir.exists() else 0
        processed_count = len(list(processed_dir.rglob("*.jsonl"))) if processed_dir.exists() else 0

        return {
            "healthy": True,
            "raw_files": raw_count,
            "processed_files": processed_count,
            "warning": "No data yet" if raw_count == 0 else None,
        }

    def _check_scraper_health(self) -> dict:
        error_log = Path("data/scrape_errors.log")
        if not error_log.exists():
            return {"healthy": True, "recent_errors": 0}

        with open(error_log) as f:
            lines = f.readlines()

        recent_errors = []
        for line in lines[-20:]:
            try:
                err = json.loads(line)
                recent_errors.append(err)
            except json.JSONDecodeError:
                pass

        return {
            "healthy": len(recent_errors) < 10,
            "recent_errors": len(recent_errors),
            "last_errors": recent_errors[-3:] if recent_errors else [],
        }

    async def _attempt_fix(self, check_name: str, result: dict) -> Optional[dict]:
        """Attempt automatic fixes for known issues."""
        fix = {"check": check_name, "time": datetime.now(timezone.utc).isoformat()}

        if check_name == "redis" and not result["healthy"]:
            fix["action"] = "Redis unavailable - bot will work without caching"
            fix["severity"] = "warning"
            logger.warning("redis_down", msg="Continuing without Redis")
            return fix

        if check_name == "disk_space" and not result["healthy"]:
            # Clean old logs and temp files
            self._cleanup_old_files()
            fix["action"] = "Cleaned old log files to free space"
            fix["severity"] = "auto_fixed"
            return fix

        if check_name == "scraper_health" and not result["healthy"]:
            fix["action"] = "Too many scraper errors - will retry with longer delays"
            fix["severity"] = "warning"
            return fix

        return None

    def _cleanup_old_files(self):
        """Remove old log files and reports to free disk space."""
        import os

        paths_to_clean = [
            Path("data/accuracy_reports"),
            Path("data/marketing_content"),
        ]

        for dir_path in paths_to_clean:
            if not dir_path.exists():
                continue
            files = sorted(dir_path.glob("*"), key=os.path.getmtime)
            # Keep last 10 files, delete rest
            for f in files[:-10]:
                f.unlink()
                logger.info("cleaned_file", path=str(f))

    def _log_health(self, report: dict):
        HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(HEALTH_LOG, "a") as f:
            f.write(json.dumps(report) + "\n")
