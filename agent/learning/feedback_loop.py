"""
Self-Learning Feedback Loop (OpenClaw-inspired)

How it works:
1. OBSERVE: Track every query → response → user reaction
2. EVALUATE: Score responses (user feedback + self-critique)
3. REINFORCE: Good answers get stored as "golden examples"
4. FILL GAPS: Bad answers trigger knowledge gap detection → auto-scrape new sources
5. EVOLVE: System prompt evolves based on accumulated learnings

This creates a flywheel:
  More users → more feedback → better answers → more users

Unlike static RAG, this system gets SMARTER over time.
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

LEARNING_DIR = Path("data/learning")
FEEDBACK_LOG = LEARNING_DIR / "feedback_log.jsonl"
GOLDEN_EXAMPLES = LEARNING_DIR / "golden_examples.jsonl"
KNOWLEDGE_GAPS = LEARNING_DIR / "knowledge_gaps.jsonl"
LEARNED_PATTERNS = LEARNING_DIR / "learned_patterns.json"


class FeedbackLoop:
    """
    Collects implicit and explicit user feedback, then uses it to improve.

    Implicit signals:
    - User asks follow-up (means answer was incomplete)
    - User rephrases (means answer was unclear)
    - User says "thank you" (means answer was good)
    - User leaves (no follow-up = answer was sufficient OR bad)

    Explicit signals:
    - Thumbs up/down buttons
    - "That's wrong" / "That's helpful"
    - User corrections ("actually it's X not Y")
    """

    def __init__(self):
        LEARNING_DIR.mkdir(parents=True, exist_ok=True)
        self.patterns = self._load_patterns()

    def record_interaction(
        self,
        query: str,
        response: str,
        intent: str,
        chunks_used: list[dict],
        language: str,
        user_id: str,
    ) -> str:
        interaction_id = hashlib.md5(f"{query}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        entry = {
            "id": interaction_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "query": query,
            "response": response[:1000],
            "intent": intent,
            "language": language,
            "chunks_used": len(chunks_used),
            "chunk_sources": [c.get("metadata", {}).get("title", "") for c in chunks_used[:3]],
            "feedback_score": None,
            "feedback_type": None,
        }

        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return interaction_id

    def record_feedback(self, interaction_id: str, score: float, feedback_type: str, user_correction: Optional[str] = None):
        """
        Score: 1.0 = perfect, 0.5 = ok, 0.0 = wrong
        feedback_type: 'thumbs_up', 'thumbs_down', 'correction', 'follow_up', 'rephrase', 'thanks'
        """
        entries = self._read_feedback_log()

        for entry in entries:
            if entry.get("id") == interaction_id:
                entry["feedback_score"] = score
                entry["feedback_type"] = feedback_type
                if user_correction:
                    entry["user_correction"] = user_correction
                break

        self._write_feedback_log(entries)

        # Trigger learning actions
        if score >= 0.8:
            self._promote_to_golden(entries[-1] if entries else None)
        elif score <= 0.3:
            self._flag_knowledge_gap(entries[-1] if entries else None, user_correction)

        logger.info("feedback_recorded", id=interaction_id, score=score, type=feedback_type)

    def detect_implicit_feedback(self, user_id: str, new_query: str, previous_query: Optional[str] = None):
        """Detect implicit signals from user behavior."""
        if not previous_query:
            return

        new_lower = new_query.lower()

        # "Thank you" signals → positive feedback
        thanks_signals = ["thank", "terima kasih", "谢谢", "tq", "thx", "helpful", "great"]
        if any(s in new_lower for s in thanks_signals):
            self._auto_rate_last_interaction(user_id, score=0.9, feedback_type="thanks")
            return

        # "That's wrong" signals → negative feedback
        wrong_signals = ["wrong", "incorrect", "salah", "不对", "no that's not", "actually it's"]
        if any(s in new_lower for s in wrong_signals):
            self._auto_rate_last_interaction(user_id, score=0.2, feedback_type="correction")
            return

        # Rephrase detection (similar query restated)
        if self._is_rephrase(previous_query, new_query):
            self._auto_rate_last_interaction(user_id, score=0.4, feedback_type="rephrase")
            return

    def _is_rephrase(self, query1: str, query2: str) -> bool:
        """Simple overlap-based rephrase detection."""
        words1 = set(query1.lower().split())
        words2 = set(query2.lower().split())
        if not words1 or not words2:
            return False
        overlap = len(words1 & words2) / max(len(words1), len(words2))
        return overlap > 0.5 and query1.lower() != query2.lower()

    def _auto_rate_last_interaction(self, user_id: str, score: float, feedback_type: str):
        entries = self._read_feedback_log()
        for entry in reversed(entries):
            if entry.get("user_id") == user_id and entry.get("feedback_score") is None:
                entry["feedback_score"] = score
                entry["feedback_type"] = feedback_type
                break
        self._write_feedback_log(entries)

    def _promote_to_golden(self, entry: Optional[dict]):
        """Store high-quality Q&A as golden examples for few-shot learning."""
        if not entry:
            return

        golden = {
            "query": entry["query"],
            "response": entry["response"],
            "intent": entry["intent"],
            "language": entry["language"],
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "score": entry.get("feedback_score", 0.9),
        }

        with open(GOLDEN_EXAMPLES, "a", encoding="utf-8") as f:
            f.write(json.dumps(golden, ensure_ascii=False) + "\n")

        logger.info("promoted_to_golden", query=entry["query"][:50])

    def _flag_knowledge_gap(self, entry: Optional[dict], correction: Optional[str] = None):
        """Flag topics where the bot performs poorly → triggers auto-learning."""
        if not entry:
            return

        gap = {
            "query": entry["query"],
            "intent": entry["intent"],
            "bad_response": entry["response"][:500],
            "user_correction": correction,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
            "resolved": False,
        }

        with open(KNOWLEDGE_GAPS, "a", encoding="utf-8") as f:
            f.write(json.dumps(gap, ensure_ascii=False) + "\n")

        logger.warning("knowledge_gap_detected", query=entry["query"][:50], intent=entry["intent"])

    def get_golden_examples(self, intent: str, limit: int = 3) -> list[dict]:
        """Retrieve golden examples for few-shot prompting."""
        if not GOLDEN_EXAMPLES.exists():
            return []

        examples = []
        with open(GOLDEN_EXAMPLES, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    ex = json.loads(line)
                    if ex.get("intent") == intent:
                        examples.append(ex)

        return sorted(examples, key=lambda x: x.get("score", 0), reverse=True)[:limit]

    def get_unresolved_gaps(self) -> list[dict]:
        """Get knowledge gaps that need to be filled."""
        if not KNOWLEDGE_GAPS.exists():
            return []

        gaps = []
        with open(KNOWLEDGE_GAPS, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    gap = json.loads(line)
                    if not gap.get("resolved"):
                        gaps.append(gap)
        return gaps

    def _load_patterns(self) -> dict:
        if LEARNED_PATTERNS.exists():
            return json.loads(LEARNED_PATTERNS.read_text())
        return {"total_interactions": 0, "positive_rate": 0, "common_gaps": []}

    def _read_feedback_log(self) -> list[dict]:
        if not FEEDBACK_LOG.exists():
            return []
        entries = []
        with open(FEEDBACK_LOG, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def _write_feedback_log(self, entries: list[dict]):
        with open(FEEDBACK_LOG, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
