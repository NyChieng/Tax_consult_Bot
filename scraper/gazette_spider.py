from bs4 import BeautifulSoup
from urllib.parse import urljoin
import structlog

from scraper.base_spider import BaseScraper, save_metadata

logger = structlog.get_logger()

GAZETTE_BASE = "https://www.federalgazette.agc.gov.my"

TAX_KEYWORDS = [
    "income tax", "cukai pendapatan", "sales tax", "service tax",
    "stamp duty", "real property gains tax", "exemption order",
    "cukai jualan", "cukai perkhidmatan", "duti setem",
]


class GazetteSpider(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="gazette",
            base_url=GAZETTE_BASE,
            output_dir="gazette",
        )

    def scrape_all(self, start_year: int = 2018):
        logger.info("starting_gazette_scrape", start_year=start_year)
        search_url = f"{GAZETTE_BASE}/search"

        for keyword in TAX_KEYWORDS:
            logger.info("searching_gazette", keyword=keyword)
            self._search_and_download(search_url, keyword, start_year)

        self.close()
        logger.info("gazette_scrape_complete")

    def _search_and_download(self, search_url: str, keyword: str, start_year: int):
        params = {"q": keyword, "year_from": start_year}
        response = self.fetch(f"{search_url}?q={keyword}&year_from={start_year}")
        if response is None:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.find_all("a", href=lambda h: h and ".pdf" in str(h))

        for link in results:
            href = link.get("href", "")
            full_url = urljoin(GAZETTE_BASE, href)
            title = link.get_text(strip=True)

            file_path = self.download_pdf(full_url, subfolder="tax_orders")
            if file_path:
                metadata = self.build_metadata(
                    url=full_url,
                    title=title,
                    section="gazette_tax_order",
                    file_type="pdf",
                )
                metadata["search_keyword"] = keyword
                save_metadata(file_path, metadata)


def run():
    spider = GazetteSpider()
    spider.scrape_all()


if __name__ == "__main__":
    run()
