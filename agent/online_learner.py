"""
Online Learner — Continuously learns from the internet.

Runs in background alongside the Telegram bot:
1. Scrapes LHDN for new updates every few hours
2. Monitors tax news RSS feeds
3. Learns from new Budget announcements
4. Stores new facts in the learning memory

This means the bot gets smarter over time WITHOUT manual intervention.
"""
import asyncio
import json
import feedparser
import httpx
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger()

KNOWLEDGE_FILE = Path("data/learning/online_knowledge.jsonl")
LAST_CHECK_FILE = Path("data/learning/last_online_check.json")

TAX_RSS_FEEDS = [
    "https://theedgemarkets.com/rss/tax",
    "https://www.thestar.com.my/rss/Business",
    "https://www.freemalaysiatoday.com/category/business/feed/",
]

LHDN_PAGES = [
    "https://www.hasil.gov.my/en/tax-updates",
    "https://www.hasil.gov.my/en/legislation/public-rulings",
]

TAX_KEYWORDS = [
    "tax", "cukai", "lhdn", "hasil", "sst", "budget", "relief",
    "deduction", "rpgt", "stamp duty", "income tax", "filing",
]


class OnlineLearner:
    def __init__(self):
        KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)

    async def learn_cycle(self):
        """Run one learning cycle — check all sources for new info."""
        logger.info("online_learning_start")

        new_facts = []

        # 1. Check RSS feeds for tax news
        news_facts = await self._check_news_feeds()
        new_facts.extend(news_facts)

        # 2. Check LHDN for updates
        lhdn_facts = await self._check_lhdn_updates()
        new_facts.extend(lhdn_facts)

        # 3. Store new facts
        if new_facts:
            self._store_facts(new_facts)
            logger.info("online_learning_done", new_facts=len(new_facts))
        else:
            logger.info("online_learning_done", new_facts=0, msg="nothing new")

        # Update last check time
        self._update_check_time()

        return new_facts

    async def _check_news_feeds(self) -> list[dict]:
        """Check RSS feeds for tax-related news."""
        facts = []

        for feed_url in TAX_RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    combined = f"{title} {summary}".lower()

                    if any(kw in combined for kw in TAX_KEYWORDS):
                        facts.append({
                            "type": "news",
                            "title": title,
                            "summary": summary[:300],
                            "url": entry.get("link", ""),
                            "date": entry.get("published", ""),
                            "source": feed_url.split("/")[2],
                            "learned_at": datetime.now(timezone.utc).isoformat(),
                        })
            except Exception as e:
                logger.warning("feed_error", url=feed_url, error=str(e))

        return facts

    async def _check_lhdn_updates(self) -> list[dict]:
        """Check LHDN website for new updates/rulings."""
        facts = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Educational Bot - MyCukai)"},
            timeout=15.0,
        ) as client:
            for url in LHDN_PAGES:
                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        continue

                    soup = BeautifulSoup(response.text, "html.parser")
                    # Look for new content items
                    links = soup.find_all("a", href=True)

                    for link in links[:20]:
                        href = link.get("href", "")
                        text = link.get_text(strip=True)

                        if len(text) > 20 and any(kw in text.lower() for kw in TAX_KEYWORDS):
                            if not self._already_known(text):
                                facts.append({
                                    "type": "lhdn_update",
                                    "title": text,
                                    "url": href if href.startswith("http") else f"https://www.hasil.gov.my{href}",
                                    "source": "hasil.gov.my",
                                    "learned_at": datetime.now(timezone.utc).isoformat(),
                                })

                except Exception as e:
                    logger.warning("lhdn_check_error", url=url, error=str(e))

        return facts

    def _already_known(self, title: str) -> bool:
        """Check if we already have this fact."""
        if not KNOWLEDGE_FILE.exists():
            return False

        title_lower = title.lower()
        with open(KNOWLEDGE_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    fact = json.loads(line)
                    if fact.get("title", "").lower() == title_lower:
                        return True
        return False

    def _store_facts(self, facts: list[dict]):
        """Append new facts to knowledge file."""
        with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
            for fact in facts:
                f.write(json.dumps(fact, ensure_ascii=False) + "\n")

    def _update_check_time(self):
        """Record when we last checked."""
        data = {"last_check": datetime.now(timezone.utc).isoformat()}
        LAST_CHECK_FILE.write_text(json.dumps(data))

    def get_recent_knowledge(self, limit: int = 10) -> list[dict]:
        """Get recently learned facts (for context injection)."""
        if not KNOWLEDGE_FILE.exists():
            return []

        facts = []
        with open(KNOWLEDGE_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    facts.append(json.loads(line))

        return facts[-limit:]


async def run_background_learner(interval_hours: int = 4):
    """Run the learner on a loop in the background."""
    learner = OnlineLearner()

    while True:
        try:
            await learner.learn_cycle()
        except Exception as e:
            logger.error("online_learner_error", error=str(e))

        # Wait before next cycle
        await asyncio.sleep(interval_hours * 3600)
