import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import structlog

from scraper.base_spider import BaseScraper, save_metadata, compute_hash, was_already_scraped, record_scrape

logger = structlog.get_logger()

NEWS_FEEDS = {
    "the_edge": "https://theedgemarkets.com/rss/tax",
    "the_star": "https://www.thestar.com.my/rss/Business",
    "nst": "https://www.nst.com.my/rss/Business",
    "bernama": "https://www.bernama.com/en/rss/business.xml",
    "fmt": "https://www.freemalaysiatoday.com/category/business/feed/",
}

TAX_KEYWORDS = [
    "tax", "cukai", "lhdn", "hasil", "sst", "budget", "belanjawan",
    "rpgt", "stamp duty", "income tax", "relief", "deduction",
]


class NewsMonitor(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="news",
            base_url="multiple",
            output_dir="news",
        )

    def scrape_all(self):
        logger.info("starting_news_monitor")
        all_articles = []

        for source_name, feed_url in NEWS_FEEDS.items():
            articles = self._fetch_feed(source_name, feed_url)
            all_articles.extend(articles)

        tax_articles = self._filter_tax_related(all_articles)
        self._save_articles(tax_articles)
        self.close()
        logger.info("news_monitor_complete", total=len(tax_articles))

    def _fetch_feed(self, source_name: str, feed_url: str) -> list[dict]:
        try:
            feed = feedparser.parse(feed_url)
            articles = []
            for entry in feed.entries[:20]:
                articles.append({
                    "source": source_name,
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", ""),
                })
            return articles
        except Exception as e:
            logger.error("feed_error", source=source_name, error=str(e))
            return []

    def _filter_tax_related(self, articles: list[dict]) -> list[dict]:
        filtered = []
        for article in articles:
            text = f"{article['title']} {article['summary']}".lower()
            if any(kw in text for kw in TAX_KEYWORDS):
                filtered.append(article)
        return filtered

    def _save_articles(self, articles: list[dict]):
        if not articles:
            return

        output_file = self.output_dir / f"news_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for article in articles:
                article["scraped_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(article, ensure_ascii=False) + "\n")

        logger.info("saved_news_articles", count=len(articles), path=str(output_file))


def run():
    monitor = NewsMonitor()
    monitor.scrape_all()


if __name__ == "__main__":
    run()
