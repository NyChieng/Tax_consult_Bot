"""
Long-Term Memory Store (OpenClaw-inspired persistent memory)

Unlike simple RAG which only retrieves documents, this gives the bot MEMORY:
- Remembers what worked for similar questions before
- Stores learned facts that aren't in official documents
- Builds a "mental model" of Malaysian tax that improves over time
- Can reference its own past correct answers

Memory Types:
1. EPISODIC: Specific Q&A episodes that went well
2. SEMANTIC: Facts and rules learned from interactions
3. PROCEDURAL: Patterns for HOW to answer different query types
4. META: Knowledge about its own performance (what it's good/bad at)
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

MEMORY_DIR = Path("data/learning/memory")


class MemoryStore:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.episodic_path = MEMORY_DIR / "episodic.jsonl"
        self.semantic_path = MEMORY_DIR / "semantic.jsonl"
        self.procedural_path = MEMORY_DIR / "procedural.json"
        self.meta_path = MEMORY_DIR / "meta_knowledge.json"

        self.procedural = self._load_json(self.procedural_path, {})
        self.meta = self._load_json(self.meta_path, {
            "strong_intents": [],
            "weak_intents": [],
            "common_mistakes": [],
            "effective_patterns": [],
        })

    def store_episode(self, query: str, response: str, intent: str, score: float, context_sources: list[str]):
        """Store a memorable interaction (high quality or instructive failure)."""
        if score < 0.7 and score > 0.3:
            return  # Only store very good or very bad episodes

        episode = {
            "id": hashlib.md5(query.encode()).hexdigest()[:10],
            "query": query,
            "response": response[:500],
            "intent": intent,
            "score": score,
            "sources_used": context_sources[:3],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "success" if score >= 0.7 else "failure",
        }

        with open(self.episodic_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(episode, ensure_ascii=False) + "\n")

    def store_fact(self, fact: str, source: str, confidence: float = 0.8):
        """Store a learned fact (e.g., from user corrections or new documents)."""
        entry = {
            "fact": fact,
            "source": source,
            "confidence": confidence,
            "learned_at": datetime.now(timezone.utc).isoformat(),
            "verified": confidence >= 0.9,
        }

        with open(self.semantic_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def learn_procedure(self, intent: str, pattern: dict):
        """Learn a procedural pattern for answering a type of question."""
        if intent not in self.procedural:
            self.procedural[intent] = []

        self.procedural[intent].append({
            "pattern": pattern,
            "learned_at": datetime.now(timezone.utc).isoformat(),
        })

        # Keep only last 10 patterns per intent
        self.procedural[intent] = self.procedural[intent][-10:]
        self._save_json(self.procedural_path, self.procedural)

    def update_meta_knowledge(self, intent: str, success: bool):
        """Update meta-knowledge about what the bot is good/bad at."""
        if success:
            if intent not in self.meta["strong_intents"]:
                self.meta["strong_intents"].append(intent)
            if intent in self.meta["weak_intents"]:
                self.meta["weak_intents"].remove(intent)
        else:
            if intent not in self.meta["weak_intents"]:
                self.meta["weak_intents"].append(intent)

        self._save_json(self.meta_path, self.meta)

    def recall_similar(self, query: str, intent: str, limit: int = 3) -> list[dict]:
        """Recall episodic memories relevant to current query."""
        if not self.episodic_path.exists():
            return []

        episodes = []
        with open(self.episodic_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    ep = json.loads(line)
                    if ep.get("intent") == intent and ep.get("type") == "success":
                        episodes.append(ep)

        # Simple keyword overlap scoring
        query_words = set(query.lower().split())
        for ep in episodes:
            ep_words = set(ep["query"].lower().split())
            ep["relevance"] = len(query_words & ep_words) / max(len(query_words), 1)

        episodes.sort(key=lambda x: x["relevance"], reverse=True)
        return episodes[:limit]

    def recall_facts(self, keywords: list[str], limit: int = 5) -> list[dict]:
        """Recall learned facts relevant to keywords."""
        if not self.semantic_path.exists():
            return []

        facts = []
        with open(self.semantic_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    fact = json.loads(line)
                    fact_lower = fact["fact"].lower()
                    if any(kw.lower() in fact_lower for kw in keywords):
                        facts.append(fact)

        facts.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return facts[:limit]

    def get_procedure(self, intent: str) -> Optional[dict]:
        """Get the best learned procedure for an intent."""
        patterns = self.procedural.get(intent, [])
        if patterns:
            return patterns[-1]["pattern"]  # Most recent = most refined
        return None

    def is_weak_area(self, intent: str) -> bool:
        """Check if this is a known weak area."""
        return intent in self.meta.get("weak_intents", [])

    def consolidate(self):
        """
        Periodic consolidation: merge duplicate facts, prune old episodes,
        update confidence scores based on accumulated evidence.
        """
        self._consolidate_facts()
        self._prune_episodes()
        logger.info("memory_consolidated")

    def _consolidate_facts(self):
        """Merge duplicate/overlapping facts, boost confidence for repeated ones."""
        if not self.semantic_path.exists():
            return

        facts = []
        with open(self.semantic_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    facts.append(json.loads(line))

        # Simple dedup by similarity
        seen_hashes = set()
        unique_facts = []
        for fact in facts:
            h = hashlib.md5(fact["fact"][:50].lower().encode()).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_facts.append(fact)
            else:
                # Boost confidence of existing fact
                for uf in unique_facts:
                    if hashlib.md5(uf["fact"][:50].lower().encode()).hexdigest() == h:
                        uf["confidence"] = min(1.0, uf["confidence"] + 0.1)
                        break

        with open(self.semantic_path, "w", encoding="utf-8") as f:
            for fact in unique_facts:
                f.write(json.dumps(fact, ensure_ascii=False) + "\n")

    def _prune_episodes(self):
        """Keep only the most valuable episodes (top 500)."""
        if not self.episodic_path.exists():
            return

        episodes = []
        with open(self.episodic_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    episodes.append(json.loads(line))

        if len(episodes) <= 500:
            return

        # Keep high-score successes and instructive failures
        episodes.sort(key=lambda x: abs(x.get("score", 0.5) - 0.5), reverse=True)
        episodes = episodes[:500]

        with open(self.episodic_path, "w", encoding="utf-8") as f:
            for ep in episodes:
                f.write(json.dumps(ep, ensure_ascii=False) + "\n")

    def _load_json(self, path: Path, default):
        if path.exists():
            return json.loads(path.read_text())
        return default

    def _save_json(self, path: Path, data):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
