import hashlib
import json
import sqlite3
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()

DATA_RAW_DIR = Path("data/raw")
SCRAPE_DB = Path("data/scraped_urls.sqlite")


def get_scrape_db() -> sqlite3.Connection:
    SCRAPE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SCRAPE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scraped_urls (
            url TEXT PRIMARY KEY,
            content_hash TEXT,
            scraped_at TEXT,
            file_path TEXT,
            status_code INTEGER
        )
    """)
    conn.commit()
    return conn


def compute_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def was_already_scraped(url: str, content_hash: str) -> bool:
    conn = get_scrape_db()
    row = conn.execute(
        "SELECT content_hash FROM scraped_urls WHERE url = ?", (url,)
    ).fetchone()
    conn.close()
    if row is None:
        return False
    return row[0] == content_hash


def record_scrape(url: str, content_hash: str, file_path: str, status_code: int):
    conn = get_scrape_db()
    conn.execute("""
        INSERT OR REPLACE INTO scraped_urls (url, content_hash, scraped_at, file_path, status_code)
        VALUES (?, ?, ?, ?, ?)
    """, (url, content_hash, datetime.now(timezone.utc).isoformat(), file_path, status_code))
    conn.commit()
    conn.close()


def save_metadata(file_path: Path, metadata: dict):
    meta_path = file_path.with_suffix(".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def polite_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    time.sleep(random.uniform(min_sec, max_sec))


class BaseScraper:
    def __init__(self, source_name: str, base_url: str, output_dir: str):
        self.source_name = source_name
        self.base_url = base_url
        self.output_dir = DATA_RAW_DIR / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (Educational Research Bot - MyCukai)"},
            follow_redirects=True,
            timeout=30.0,
        )
        self.errors: list[dict] = []

    def fetch(self, url: str) -> Optional[httpx.Response]:
        try:
            polite_delay()
            response = self.client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("rate_limited", url=url)
                time.sleep(600)
                return self.fetch(url)
            self.errors.append({"url": url, "error": str(e), "time": datetime.now(timezone.utc).isoformat()})
            logger.error("http_error", url=url, status=e.response.status_code)
            return None
        except Exception as e:
            self.errors.append({"url": url, "error": str(e), "time": datetime.now(timezone.utc).isoformat()})
            logger.error("fetch_error", url=url, error=str(e))
            return None

    def download_pdf(self, url: str, subfolder: str = "") -> Optional[Path]:
        response = self.fetch(url)
        if response is None:
            return None

        content_hash = compute_hash(response.content)
        if was_already_scraped(url, content_hash):
            logger.info("skipping_unchanged", url=url)
            return None

        target_dir = self.output_dir / subfolder if subfolder else self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = url.split("/")[-1]
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        file_path = target_dir / filename

        with open(file_path, "wb") as f:
            f.write(response.content)

        record_scrape(url, content_hash, str(file_path), response.status_code)
        logger.info("downloaded", url=url, path=str(file_path))
        return file_path

    def build_metadata(self, url: str, title: str, section: str, file_type: str, language: str = "en") -> dict:
        return {
            "source_url": url,
            "source_domain": self.base_url.replace("https://", "").replace("http://", "").split("/")[0],
            "source_type": "official_government",
            "title": title,
            "section": section,
            "file_type": file_type,
            "language": language,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "scraper": self.source_name,
        }

    def save_errors(self):
        if self.errors:
            error_path = Path("data") / "scrape_errors.log"
            with open(error_path, "a", encoding="utf-8") as f:
                for err in self.errors:
                    f.write(json.dumps(err) + "\n")

    def close(self):
        self.save_errors()
        self.client.close()
