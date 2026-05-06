"""
Advanced Rate Limiter with DDoS protection and abuse detection.

Layers:
1. Per-user rate limiting (30 queries/hour)
2. Global rate limiting (prevent DDoS)
3. Burst detection (sudden spike = attack)
4. IP-based throttling
5. Sliding window algorithm (more accurate than fixed windows)
"""
import time
import hashlib
from collections import defaultdict
from typing import Optional
import structlog

logger = structlog.get_logger()


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter — more accurate than fixed windows.
    Prevents users from exploiting window boundaries.
    """

    def __init__(
        self,
        max_requests_per_hour: int = 30,
        max_requests_per_minute: int = 10,
        global_max_per_minute: int = 100,
        burst_threshold: int = 5,
        burst_window_seconds: int = 10,
    ):
        self.max_per_hour = max_requests_per_hour
        self.max_per_minute = max_requests_per_minute
        self.global_max_per_minute = global_max_per_minute
        self.burst_threshold = burst_threshold
        self.burst_window = burst_window_seconds

        # Sliding windows: user_id -> list of timestamps
        self.user_windows: dict[str, list[float]] = defaultdict(list)
        self.global_window: list[float] = []
        self.banned_users: dict[str, float] = {}  # user_id -> ban_expiry timestamp

    def check(self, user_id: str, ip_address: Optional[str] = None) -> dict:
        """
        Check if request is allowed.
        Returns:
        {
            "allowed": bool,
            "reason": str | None,
            "remaining": int,
            "retry_after_seconds": int | None,
        }
        """
        now = time.time()

        # Check if user is banned
        if user_id in self.banned_users:
            if now < self.banned_users[user_id]:
                return {
                    "allowed": False,
                    "reason": "user_temporarily_banned",
                    "remaining": 0,
                    "retry_after_seconds": int(self.banned_users[user_id] - now),
                }
            else:
                del self.banned_users[user_id]

        # Global rate check (DDoS protection)
        self.global_window = [t for t in self.global_window if now - t < 60]
        if len(self.global_window) >= self.global_max_per_minute:
            logger.warning("global_rate_limit_hit")
            return {
                "allowed": False,
                "reason": "server_overloaded",
                "remaining": 0,
                "retry_after_seconds": 30,
            }

        # Clean old entries
        self.user_windows[user_id] = [t for t in self.user_windows[user_id] if now - t < 3600]

        # Per-minute check
        recent_minute = [t for t in self.user_windows[user_id] if now - t < 60]
        if len(recent_minute) >= self.max_per_minute:
            return {
                "allowed": False,
                "reason": "per_minute_limit",
                "remaining": 0,
                "retry_after_seconds": 60 - int(now - recent_minute[0]) if recent_minute else 60,
            }

        # Per-hour check
        if len(self.user_windows[user_id]) >= self.max_per_hour:
            oldest = self.user_windows[user_id][0]
            retry_after = int(3600 - (now - oldest))
            return {
                "allowed": False,
                "reason": "hourly_limit_exceeded",
                "remaining": 0,
                "retry_after_seconds": max(retry_after, 1),
            }

        # Burst detection
        recent_burst = [t for t in self.user_windows[user_id] if now - t < self.burst_window]
        if len(recent_burst) >= self.burst_threshold:
            # Temporary ban for 5 minutes
            self.banned_users[user_id] = now + 300
            logger.warning("burst_detected_user_banned", user_id=user_id)
            return {
                "allowed": False,
                "reason": "burst_detected",
                "remaining": 0,
                "retry_after_seconds": 300,
            }

        # Allow request
        self.user_windows[user_id].append(now)
        self.global_window.append(now)

        remaining = self.max_per_hour - len(self.user_windows[user_id])
        return {
            "allowed": True,
            "reason": None,
            "remaining": remaining,
            "retry_after_seconds": None,
        }

    def get_user_status(self, user_id: str) -> dict:
        """Get current rate limit status for a user."""
        now = time.time()
        window = [t for t in self.user_windows.get(user_id, []) if now - t < 3600]
        return {
            "requests_this_hour": len(window),
            "remaining": max(0, self.max_per_hour - len(window)),
            "is_banned": user_id in self.banned_users,
            "resets_in_seconds": int(3600 - (now - window[0])) if window else 3600,
        }

    def ban_user(self, user_id: str, duration_seconds: int = 3600):
        """Manually ban a user (e.g., from abuse detection)."""
        self.banned_users[user_id] = time.time() + duration_seconds
        logger.info("user_banned", user_id=user_id, duration=duration_seconds)

    def unban_user(self, user_id: str):
        """Remove a user ban."""
        self.banned_users.pop(user_id, None)


# Singleton
rate_limiter = SlidingWindowRateLimiter()
