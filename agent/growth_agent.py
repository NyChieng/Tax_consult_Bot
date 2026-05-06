"""
Growth Agent - Autonomous marketing and user acquisition.

Handles:
- SEO blog post generation
- Social media scheduling
- Competitor monitoring
- User onboarding optimization
- A/B test suggestions
"""
import anthropic
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import structlog

from config import settings

logger = structlog.get_logger()

OUTPUT_DIR = Path("data/marketing_content")


class GrowthAgent:
    def __init__(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.client = None
        if settings.anthropic_api_key:
            self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_seo_blog_post(self, keyword: str) -> dict:
        """Generate a full SEO-optimized blog post for a target keyword."""
        if not self.client:
            return {"error": "No API key configured"}

        prompt = f"""Write a comprehensive SEO blog post about "{keyword}" for Malaysian taxpayers.

Requirements:
- Title: Include the exact keyword, under 60 characters
- Meta description: 150-160 characters with keyword
- Structure: H1, then H2 sections, with H3 subsections
- Length: 1500-2000 words
- Tone: Friendly, educational, not overly formal
- Include: Specific Malaysian tax rates, RM amounts, LHDN references
- Include: FAQ section at the end (5 common questions)
- CTA: Mention MyCukai bot at natural points (not spammy)
- Add disclaimer at end (this is reference only, consult tax agent)

Target audience: Malaysian individuals and small business owners
Language: English (with occasional BM terms that Malaysians use)

Format as JSON:
{{
  "title": "...",
  "meta_description": "...",
  "slug": "...",
  "content_html": "...",
  "word_count": ...,
  "target_keyword": "...",
  "secondary_keywords": [...],
  "faq": [...]
}}"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            result = json.loads(text[start:end])
        except Exception:
            result = {"raw_content": text, "keyword": keyword}

        # Save to file
        safe_keyword = keyword.replace(" ", "_")[:50]
        output_path = OUTPUT_DIR / f"blog_{safe_keyword}_{datetime.now().strftime('%Y%m%d')}.json"
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        return result

    async def generate_weekly_content_plan(self) -> dict:
        """Create a full week's content plan across all channels."""
        if not self.client:
            return _fallback_weekly_plan()

        prompt = """Create a 7-day social media content plan for MyCukai (Malaysian AI tax bot).

For each day (Monday to Sunday), provide:
1. Platform to post on
2. Content type (video, carousel, thread, post)
3. Topic/hook
4. Full draft text
5. Best posting time (MYT)
6. Hashtags

Channels: TikTok, Instagram, Twitter/X, Facebook, LinkedIn, Telegram

Rules:
- Monday: Educational (long-form)
- Tuesday-Thursday: Tips & tricks (short, shareable)
- Friday: Engagement/polls
- Saturday: User stories / testimonials format
- Sunday: Week-ahead reminder (deadlines, etc.)

All content should be Malaysia-specific with real tax info.
CTA should mention @MyCukaiBot on Telegram.

Format as JSON array of 7 day objects."""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        try:
            start = text.find("[")
            end = text.rfind("]") + 1
            plan = json.loads(text[start:end])
        except Exception:
            plan = {"raw": text}

        result = {
            "week_of": datetime.now().strftime("%Y-%m-%d"),
            "plan": plan,
            "generated_at": datetime.now().isoformat(),
        }

        output_path = OUTPUT_DIR / f"weekly_plan_{datetime.now().strftime('%Y%m%d')}.json"
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        return result

    async def analyze_competitor_content(self, competitor_name: str = "general") -> dict:
        """Generate competitive positioning suggestions."""
        if not self.client:
            return {"status": "no_api_key"}

        prompt = f"""Analyze the competitive landscape for an AI tax assistant in Malaysia and provide:

1. Key differentiators MyCukai should emphasize
2. Content gaps competitors aren't filling
3. Messaging angles that would resonate with Malaysian taxpayers
4. Pricing positioning advice
5. Partnership opportunities unique to the Malaysian market

Consider:
- Big 4 firms have tax content but it's complex/corporate-focused
- LHDN has info but it's hard to navigate
- No existing AI chatbot covers Malaysian tax
- Chinese-language tax content is severely underserved
- Tax agents are expensive (RM 200-2000/consultation)

Format as actionable recommendations."""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        return {
            "analysis": response.content[0].text,
            "generated_at": datetime.now().isoformat(),
        }

    async def generate_onboarding_sequence(self) -> dict:
        """Create a 7-message onboarding drip sequence for new users."""
        if not self.client:
            return {"status": "no_api_key"}

        prompt = """Create a 7-message Telegram onboarding sequence for new MyCukai users.
Send one message per day for 7 days after signup.

Each message should:
- Be under 200 words
- Teach one specific tax tip
- Encourage them to ask the bot a question
- Build towards paid conversion by Day 7

Day 1: Welcome + show what the bot can do
Day 2: Personal relief tip (most popular topic)
Day 3: e-Filing tip (practical value)
Day 4: SME-specific tip (target business users)
Day 5: "Did you know?" surprising fact
Day 6: Deadline reminder value prop
Day 7: Soft sell to upgrade (mention premium features)

Language: Mix of English and BM (natural Malaysian style)
Format as JSON array of 7 message objects with: day, subject, message, cta"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        try:
            start = text.find("[")
            end = text.rfind("]") + 1
            sequence = json.loads(text[start:end])
        except Exception:
            sequence = {"raw": text}

        return {
            "sequence": sequence,
            "generated_at": datetime.now().isoformat(),
        }


def _fallback_weekly_plan() -> dict:
    return {
        "week_of": datetime.now().strftime("%Y-%m-%d"),
        "plan": [
            {"day": "Monday", "platform": "LinkedIn", "type": "long post", "topic": "SME tax incentives breakdown"},
            {"day": "Tuesday", "platform": "TikTok", "type": "60s video", "topic": "Tax relief you didn't know about"},
            {"day": "Wednesday", "platform": "Facebook", "type": "infographic", "topic": "2025 tax rate comparison"},
            {"day": "Thursday", "platform": "Twitter", "type": "thread", "topic": "e-Filing step by step"},
            {"day": "Friday", "platform": "Instagram", "type": "poll/story", "topic": "Can you claim this? Quiz"},
            {"day": "Saturday", "platform": "TikTok", "type": "60s video", "topic": "RPGT explained simply"},
            {"day": "Sunday", "platform": "Telegram", "type": "weekly digest", "topic": "Tax news roundup"},
        ],
    }
