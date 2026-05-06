"""
Analytics Agent - Tracks user behavior and generates insights automatically.

Monitors:
- Query patterns (what people ask most)
- Conversion opportunities (when to suggest paid tier)
- Knowledge gaps (questions the bot can't answer well)
- User segments (individual vs SME vs agent)
- Peak usage times
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import Optional
import structlog

logger = structlog.get_logger()

ANALYTICS_DIR = Path("data/analytics")


class AnalyticsAgent:
    def __init__(self):
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        self.query_log_path = ANALYTICS_DIR / "query_log.jsonl"
        self.insights_path = ANALYTICS_DIR / "insights.json"

    def log_query(self, user_id: str, query: str, intent: str, language: str, response_quality: Optional[float] = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "query": query,
            "intent": intent,
            "language": language,
            "response_quality": response_quality,
        }
        with open(self.query_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def generate_insights(self) -> dict:
        """Analyze all queries and produce actionable insights."""
        if not self.query_log_path.exists():
            return {"status": "no_data"}

        queries = []
        with open(self.query_log_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    queries.append(json.loads(line))

        if not queries:
            return {"status": "no_data"}

        # Intent distribution
        intents = Counter(q["intent"] for q in queries)
        top_intents = intents.most_common(10)

        # Language distribution
        languages = Counter(q["language"] for q in queries)

        # Unique users
        unique_users = len(set(q["user_id"] for q in queries))

        # Peak hours (UTC)
        hours = Counter(q["timestamp"][11:13] for q in queries)
        peak_hours = hours.most_common(3)

        # Knowledge gaps (low quality responses)
        low_quality = [q for q in queries if q.get("response_quality") and q["response_quality"] < 0.5]
        gap_intents = Counter(q["intent"] for q in low_quality).most_common(5)

        # Daily query volume
        days = Counter(q["timestamp"][:10] for q in queries)

        insights = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_queries": len(queries),
            "unique_users": unique_users,
            "avg_queries_per_user": round(len(queries) / max(unique_users, 1), 1),
            "top_intents": [{"intent": i, "count": c} for i, c in top_intents],
            "language_split": dict(languages),
            "peak_hours_utc": [{"hour": h, "count": c} for h, c in peak_hours],
            "knowledge_gaps": [{"intent": i, "low_quality_count": c} for i, c in gap_intents],
            "daily_volume": dict(sorted(days.items())[-7:]),
            "recommendations": self._generate_recommendations(
                intents, languages, unique_users, len(queries), gap_intents
            ),
        }

        self.insights_path.write_text(json.dumps(insights, indent=2))
        return insights

    def _generate_recommendations(self, intents, languages, users, total, gaps) -> list[str]:
        recs = []

        # Content recommendations
        top_intent = intents.most_common(1)[0][0] if intents else None
        if top_intent:
            recs.append(f"Create more content about '{top_intent}' — it's your #1 queried topic")

        # Language recommendations
        if languages.get("zh", 0) > total * 0.2:
            recs.append("Chinese queries are 20%+ — invest in ZH content marketing")
        if languages.get("bm", 0) > total * 0.3:
            recs.append("Strong BM demand — create BM-specific TikTok content")

        # Conversion recommendations
        if users > 100:
            recs.append(f"You have {users} users — time to introduce freemium wall")

        # Gap recommendations
        if gaps:
            gap_intent = gaps[0][0]
            recs.append(f"Knowledge gap detected in '{gap_intent}' — add more source docs for this topic")

        return recs

    def get_conversion_candidates(self) -> list[dict]:
        """Identify users who should be prompted to upgrade."""
        if not self.query_log_path.exists():
            return []

        user_counts: dict[str, int] = {}
        with open(self.query_log_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    q = json.loads(line)
                    uid = q["user_id"]
                    user_counts[uid] = user_counts.get(uid, 0) + 1

        # Users with 8+ queries are approaching free limit
        candidates = [
            {"user_id": uid, "query_count": count, "suggest_upgrade": True}
            for uid, count in user_counts.items()
            if count >= 8
        ]

        return sorted(candidates, key=lambda x: x["query_count"], reverse=True)
