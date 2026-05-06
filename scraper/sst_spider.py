from bs4 import BeautifulSoup
from urllib.parse import urljoin
import structlog

from scraper.base_spider import BaseScraper, save_metadata

logger = structlog.get_logger()

MYSST_BASE = "https://mysst.customs.gov.my"
CUSTOMS_BASE = "https://www.customs.gov.my"

SST_PATHS = [
    "/en/pp/Pages/sst.aspx",
    "/en/pp/Pages/sst-guides.aspx",
    "/en/pp/Pages/sst-orders.aspx",
]


class SSTSpider(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="sst",
            base_url=CUSTOMS_BASE,
            output_dir="sst",
        )

    def scrape_all(self):
        logger.info("starting_sst_scrape")
        self._scrape_customs_sst()
        self._scrape_mysst_portal()
        self.close()
        logger.info("sst_scrape_complete")

    def _scrape_customs_sst(self):
        for path in SST_PATHS:
            url = f"{CUSTOMS_BASE}{path}"
            response = self.fetch(url)
            if response is None:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            pdf_links = soup.find_all("a", href=lambda h: h and ".pdf" in str(h))

            for link in pdf_links:
                href = link.get("href", "")
                full_url = urljoin(url, href)
                title = link.get_text(strip=True) or href.split("/")[-1]

                file_path = self.download_pdf(full_url, subfolder="customs_guides")
                if file_path:
                    metadata = self.build_metadata(
                        url=full_url,
                        title=title,
                        section="sst_guides",
                        file_type="pdf",
                    )
                    metadata["source_type"] = "official_government"
                    metadata["tax_category"] = ["sst"]
                    save_metadata(file_path, metadata)

    def _scrape_mysst_portal(self):
        url = MYSST_BASE
        response = self.fetch(url)
        if response is None:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        pdf_links = soup.find_all("a", href=lambda h: h and ".pdf" in str(h))

        for link in pdf_links:
            href = link.get("href", "")
            full_url = urljoin(MYSST_BASE, href)
            title = link.get_text(strip=True)

            file_path = self.download_pdf(full_url, subfolder="mysst")
            if file_path:
                metadata = self.build_metadata(
                    url=full_url,
                    title=title,
                    section="mysst_portal",
                    file_type="pdf",
                )
                metadata["tax_category"] = ["sst"]
                save_metadata(file_path, metadata)


def run():
    spider = SSTSpider()
    spider.scrape_all()


if __name__ == "__main__":
    run()
