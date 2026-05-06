from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import structlog

from scraper.base_spider import BaseScraper, save_metadata

logger = structlog.get_logger()

LHDN_BASE = "https://www.hasil.gov.my"

SECTIONS = {
    "public_rulings": "/en/legislation/public-rulings",
    "practice_notes": "/en/legislation/practice-notes",
    "guidelines_individual": "/en/individual/guidelines",
    "guidelines_business": "/en/business/guidelines",
    "faqs": "/en/faqs",
    "forms": "/en/forms",
    "tax_updates": "/en/tax-updates",
}


class LHDNSpider(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="lhdn",
            base_url=LHDN_BASE,
            output_dir="lhdn",
        )

    def scrape_all(self):
        logger.info("starting_lhdn_scrape")
        for section_name, path in SECTIONS.items():
            logger.info("scraping_section", section=section_name)
            self._scrape_section(section_name, path)
        self.close()
        logger.info("lhdn_scrape_complete")

    def _scrape_section(self, section_name: str, path: str):
        url = f"{LHDN_BASE}{path}"
        response = self.fetch(url)
        if response is None:
            return

        soup = BeautifulSoup(response.text, "html.parser")

        if section_name == "faqs":
            self._extract_faqs(soup, url, section_name)
        else:
            self._extract_documents(soup, url, section_name)

    def _extract_documents(self, soup: BeautifulSoup, page_url: str, section_name: str):
        pdf_links = soup.find_all("a", href=lambda h: h and h.endswith(".pdf"))

        for link in pdf_links:
            href = link.get("href", "")
            full_url = urljoin(page_url, href)
            title = link.get_text(strip=True) or href.split("/")[-1]

            file_path = self.download_pdf(full_url, subfolder=section_name)
            if file_path:
                metadata = self.build_metadata(
                    url=full_url,
                    title=title,
                    section=section_name,
                    file_type="pdf",
                )
                save_metadata(file_path, metadata)

        html_links = soup.find_all("a", href=lambda h: h and not h.endswith(".pdf") and "/en/" in str(h))
        for link in html_links[:50]:
            href = link.get("href", "")
            if href.startswith("#") or "javascript:" in href:
                continue
            full_url = urljoin(page_url, href)
            self._scrape_html_page(full_url, section_name)

    def _scrape_html_page(self, url: str, section_name: str):
        response = self.fetch(url)
        if response is None:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
        if not main_content:
            return

        for tag in main_content.find_all(["nav", "header", "footer", "aside", "script", "style"]):
            tag.decompose()

        text = main_content.get_text(separator="\n", strip=True)
        if len(text) < 100:
            return

        title = soup.find("h1")
        title_text = title.get_text(strip=True) if title else url.split("/")[-1]

        filename = url.split("/")[-1].replace(".html", "") or "index"
        file_path = self.output_dir / section_name / f"{filename}.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        metadata = self.build_metadata(
            url=url,
            title=title_text,
            section=section_name,
            file_type="html",
        )
        save_metadata(file_path, metadata)

    def _extract_faqs(self, soup: BeautifulSoup, page_url: str, section_name: str):
        faq_items = []
        questions = soup.find_all(["h3", "h4", "dt", "button"], class_=lambda c: c and "faq" in str(c).lower()) or \
                    soup.find_all("div", class_=lambda c: c and ("accordion" in str(c).lower() or "faq" in str(c).lower()))

        if not questions:
            questions = soup.find_all(["h3", "h4"])

        for q in questions:
            question_text = q.get_text(strip=True)
            answer_el = q.find_next_sibling(["p", "div", "dd"])
            answer_text = answer_el.get_text(strip=True) if answer_el else ""
            if question_text and answer_text:
                faq_items.append({"question": question_text, "answer": answer_text})

        if faq_items:
            import json
            file_path = self.output_dir / section_name / "faqs.jsonl"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                for item in faq_items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            metadata = self.build_metadata(
                url=page_url,
                title="LHDN FAQs",
                section=section_name,
                file_type="jsonl",
            )
            save_metadata(file_path, metadata)
            logger.info("extracted_faqs", count=len(faq_items))


def run():
    spider = LHDNSpider()
    spider.scrape_all()


if __name__ == "__main__":
    run()
