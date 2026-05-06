from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path
import json
import structlog

from scraper.base_spider import BaseScraper, save_metadata, compute_hash, was_already_scraped, record_scrape

logger = structlog.get_logger()

BIG4_SOURCES = {
    "deloitte": {
        "url": "https://www2.deloitte.com/my/en/pages/tax/articles/tax-alerts.html",
        "base": "https://www2.deloitte.com",
    },
    "pwc": {
        "url": "https://www.pwc.com/my/en/tax-publications.html",
        "base": "https://www.pwc.com",
    },
    "kpmg": {
        "url": "https://kpmg.com/my/en/home/insights/tax.html",
        "base": "https://kpmg.com",
    },
    "ey": {
        "url": "https://www.ey.com/en_my/tax",
        "base": "https://www.ey.com",
    },
}


class Big4Spider(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="big4",
            base_url="multiple",
            output_dir="big4",
        )

    def scrape_all(self):
        logger.info("starting_big4_scrape")
        for firm_name, config in BIG4_SOURCES.items():
            logger.info("scraping_firm", firm=firm_name)
            self._scrape_firm(firm_name, config["url"], config["base"])
        self.close()
        logger.info("big4_scrape_complete")

    def _scrape_firm(self, firm_name: str, url: str, base_url: str):
        response = self.fetch(url)
        if response is None:
            return

        soup = BeautifulSoup(response.text, "html.parser")

        articles = soup.find_all("a", href=lambda h: h and (
            "article" in str(h) or "alert" in str(h) or "insight" in str(h) or "tax" in str(h)
        ))

        seen_urls = set()
        for link in articles[:30]:
            href = link.get("href", "")
            if href in seen_urls or href.startswith("#"):
                continue
            seen_urls.add(href)

            full_url = urljoin(base_url, href)
            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            self._scrape_article(firm_name, full_url, title)

    def _scrape_article(self, firm_name: str, url: str, title: str):
        response = self.fetch(url)
        if response is None:
            return

        content_hash = compute_hash(response.content)
        if was_already_scraped(url, content_hash):
            return

        soup = BeautifulSoup(response.text, "html.parser")
        main = soup.find("article") or soup.find("main") or soup.find("div", class_="content")
        if not main:
            return

        for tag in main.find_all(["nav", "header", "footer", "aside", "script", "style"]):
            tag.decompose()

        text = main.get_text(separator="\n", strip=True)
        if len(text) < 200:
            return

        target_dir = self.output_dir / firm_name
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:80]
        file_path = target_dir / f"{safe_title}.txt"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        record_scrape(url, content_hash, str(file_path), 200)

        metadata = self.build_metadata(
            url=url,
            title=title,
            section=f"big4_{firm_name}",
            file_type="html",
        )
        metadata["source_type"] = "professional_commentary"
        metadata["firm"] = firm_name
        save_metadata(file_path, metadata)
        logger.info("saved_article", firm=firm_name, title=title[:50])


def run():
    spider = Big4Spider()
    spider.scrape_all()


if __name__ == "__main__":
    run()
