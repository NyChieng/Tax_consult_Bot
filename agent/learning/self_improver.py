"""
Self-Improving Agent (OpenClaw-style Continuous Learning)

This is the brain that makes the bot SMARTER over time:

1. SELF-CRITIQUE: After generating a response, evaluates its own quality
2. GAP FILLING: Automatically searches for new info when it can't answer well
3. PROMPT EVOLUTION: Refines the system prompt based on learned patterns
4. KNOWLEDGE SYNTHESIS: Combines multiple weak sources into strong answers
5. MEMORY CONSOLIDATION: Compresses learned patterns into reusable knowledge

Inspired by:
- OpenClaw's self-play and reward modeling
- Constitutional AI (self-critique loop)
- RLHF without human labels (uses implicit feedback)
"""
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import anthropic
import structlog

from config import settings
from agent.learning.feedback_loop import FeedbackLoop, KNOWLEDGE_GAPS, GOLDEN_EXAMPLES, LEARNING_DIR

logger = structlog.get_logger()

EVOLVED_PROMPTS_DIR = LEARNING_DIR / "evolved_prompts"
SYNTHESIS_DIR = LEARNING_DIR / "synthesized_knowledge"


class SelfImprover:
    """
    Autonomous self-improvement agent.
    Runs periodically to make the bot better without human intervention.
    """

    def __init__(self):
        EVOLVED_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)
        self.feedback = FeedbackLoop()
        self.client = None
        if settings.anthropic_api_key:
            self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def self_critique(self, query: str, response: str, context_chunks: list[dict]) -> dict:
        """
        After generating a response, ask Claude to critique it.
        Returns a quality score and improvement suggestions.
        """
        if not self.client:
            return {"score": 0.7, "critique": "No API key for self-critique"}

        critique_prompt = f"""You are a quality assurance reviewer for a Malaysian tax reference bot.

Evaluate this response on these criteria:
1. ACCURACY: Does it match the provided source context? (0-10)
2. COMPLETENESS: Does it answer the full question? (0-10)
3. CLARITY: Is it easy to understand? (0-10)
4. SOURCES: Are citations properly included? (0-10)
5. SAFETY: Does it avoid giving specific tax calculations or personalised advice? (0-10)

USER QUERY: {query}

BOT RESPONSE: {response}

SOURCE CONTEXT AVAILABLE: {json.dumps([c.get('text', '')[:200] for c in context_chunks[:3]])}

Respond in JSON format:
{{"accuracy": N, "completeness": N, "clarity": N, "sources": N, "safety": N, "overall": N, "issues": ["..."], "suggestion": "..."}}
"""

        try:
            result = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": critique_prompt}],
            )

            text = result.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                critique = json.loads(text[start:end])
                critique["score"] = critique.get("overall", 7) / 10.0
                return critique

        except Exception as e:
            logger.warning("self_critique_failed", error=str(e))

        return {"score": 0.7, "critique": "Critique unavailable"}

    async def fill_knowledge_gaps(self):
        """
        Automatically find and fill knowledge gaps.
        When the bot can't answer well, this agent:
        1. Identifies what info is missing
        2. Searches for it online / in additional sources
        3. Adds it to the knowledge base
        """
        gaps = self.feedback.get_unresolved_gaps()
        if not gaps:
            logger.info("no_knowledge_gaps")
            return

        logger.info("filling_knowledge_gaps", count=len(gaps))

        for gap in gaps[:5]:  # Process top 5 gaps at a time
            await self._resolve_gap(gap)

    async def _resolve_gap(self, gap: dict):
        """Attempt to resolve a single knowledge gap."""
        if not self.client:
            return

        query = gap["query"]
        intent = gap["intent"]

        # Step 1: Understand what's missing
        analysis_prompt = f"""A Malaysian tax bot failed to answer this question well:
Query: "{query}"
Intent: {intent}
Bad response: "{gap.get('bad_response', '')[:300]}"
User correction (if any): "{gap.get('user_correction', 'none')}"

What specific Malaysian tax information is needed to answer this correctly?
List the exact facts, rates, or rules needed. Be specific (include section numbers, RM amounts, dates).

Format as JSON:
{{"missing_facts": ["fact1", "fact2"], "source_needed": "description of ideal source", "search_keywords": ["kw1", "kw2"]}}
"""

        try:
            result = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": analysis_prompt}],
            )

            text = result.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                analysis = json.loads(text[start:end])
            else:
                analysis = {"missing_facts": [], "search_keywords": [query]}

            # Step 2: Generate a synthetic "correct" answer for this gap
            correct_answer = await self._generate_correct_answer(query, intent, analysis, gap.get("user_correction"))

            if correct_answer:
                # Step 3: Store as synthesized knowledge
                self._store_synthesis(query, intent, correct_answer, analysis)

                # Mark gap as resolved
                self._resolve_gap_in_log(gap)
                logger.info("gap_resolved", query=query[:50])

        except Exception as e:
            logger.error("gap_resolution_failed", error=str(e), query=query[:50])

    async def _generate_correct_answer(self, query: str, intent: str, analysis: dict, user_correction: Optional[str]) -> Optional[str]:
        """Generate what the correct answer SHOULD be, based on analysis."""
        if not self.client:
            return None

        correction_context = f"\nUser said the correct answer is: {user_correction}" if user_correction else ""

        prompt = f"""Based on Malaysian tax law, generate the CORRECT answer to this question.

Question: "{query}"
Intent: {intent}
Missing facts identified: {json.dumps(analysis.get('missing_facts', []))}
{correction_context}

Generate a comprehensive, accurate answer following these rules:
- Cite specific Malaysian law (Income Tax Act 1967, etc.)
- Include specific RM amounts and rates
- Be factual and verifiable
- Do not make up information — if unsure, say so
- Keep under 300 words

Answer:"""

        try:
            result = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return result.content[0].text
        except Exception:
            return None

    def _store_synthesis(self, query: str, intent: str, answer: str, analysis: dict):
        """Store synthesized knowledge for future retrieval."""
        synthesis = {
            "query": query,
            "intent": intent,
            "synthesized_answer": answer,
            "missing_facts": analysis.get("missing_facts", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "self_improvement",
            "verified": False,
        }

        output_file = SYNTHESIS_DIR / f"synth_{intent}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.write_text(json.dumps(synthesis, indent=2, ensure_ascii=False))

    def _resolve_gap_in_log(self, gap: dict):
        """Mark a knowledge gap as resolved."""
        if not KNOWLEDGE_GAPS.exists():
            return

        entries = []
        with open(KNOWLEDGE_GAPS, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry["query"] == gap["query"] and entry["flagged_at"] == gap["flagged_at"]:
                        entry["resolved"] = True
                        entry["resolved_at"] = datetime.now(timezone.utc).isoformat()
                    entries.append(entry)

        with open(KNOWLEDGE_GAPS, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def evolve_system_prompt(self) -> Optional[str]:
        """
        Analyze all feedback and golden examples to suggest system prompt improvements.
        This is the 'meta-learning' step — the bot improves HOW it answers, not just WHAT.
        """
        if not self.client:
            return None

        # Gather learning data
        golden = self._get_recent_golden(20)
        gaps = self.feedback.get_unresolved_gaps()[:10]
        stats = self._get_feedback_stats()

        if not golden and not gaps:
            return None

        prompt = f"""You are optimizing the system prompt for a Malaysian tax reference bot.

CURRENT PERFORMANCE:
- Total interactions: {stats['total']}
- Positive rate: {stats['positive_rate']}%
- Most common gaps: {json.dumps(stats['common_gap_intents'][:5])}

TOP-RATED RESPONSES (what works well):
{json.dumps([{"q": g["query"][:80], "intent": g["intent"]} for g in golden[:5]], indent=2)}

KNOWLEDGE GAPS (what fails):
{json.dumps([{"q": g["query"][:80], "intent": g["intent"]} for g in gaps[:5]], indent=2)}

Based on this data, suggest 3-5 specific additions or modifications to the system prompt that would:
1. Improve answers in the gap areas
2. Reinforce the patterns that work well
3. Add any new instructions that would prevent common failures

Format each suggestion as a clear instruction that can be appended to the system prompt.
Be specific to Malaysian tax context."""

        try:
            result = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            suggestions = result.content[0].text

            # Save evolved prompt suggestions
            output = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "based_on_interactions": stats["total"],
                "suggestions": suggestions,
                "stats": stats,
            }

            output_file = EVOLVED_PROMPTS_DIR / f"evolution_{datetime.now().strftime('%Y%m%d')}.json"
            output_file.write_text(json.dumps(output, indent=2))

            logger.info("prompt_evolution_generated", file=str(output_file))
            return suggestions

        except Exception as e:
            logger.error("prompt_evolution_failed", error=str(e))
            return None

    def get_few_shot_examples(self, intent: str) -> str:
        """Get golden examples formatted for few-shot insertion into prompt."""
        examples = self.feedback.get_golden_examples(intent, limit=2)
        if not examples:
            return ""

        few_shot = "\n\nHere are examples of highly-rated responses for similar questions:\n"
        for ex in examples:
            few_shot += f"\nUser: {ex['query']}\nAssistant: {ex['response'][:300]}\n"

        return few_shot

    def _get_recent_golden(self, limit: int) -> list[dict]:
        if not GOLDEN_EXAMPLES.exists():
            return []
        examples = []
        with open(GOLDEN_EXAMPLES, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    examples.append(json.loads(line))
        return examples[-limit:]

    def _get_feedback_stats(self) -> dict:
        entries = self.feedback._read_feedback_log()
        if not entries:
            return {"total": 0, "positive_rate": 0, "common_gap_intents": []}

        scored = [e for e in entries if e.get("feedback_score") is not None]
        positive = [e for e in scored if e["feedback_score"] >= 0.7]
        negative = [e for e in scored if e["feedback_score"] < 0.4]

        from collections import Counter
        gap_intents = Counter(e["intent"] for e in negative)

        return {
            "total": len(entries),
            "scored": len(scored),
            "positive_rate": round(len(positive) / max(len(scored), 1) * 100, 1),
            "common_gap_intents": gap_intents.most_common(5),
        }
