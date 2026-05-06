import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx
import structlog

from scraper.base_spider import get_scrape_db

logger = structlog.get_logger()

CRITICAL_URLS = [
    "https://www.hasil.gov.my/en/legislation/public-rulings",
    "https://www.hasil.gov.my/en/tax-updates",
    "https://www.hasil.gov.my/en/individual/guidelines",
    "https://mysst.customs.gov.my",
]


def check_freshness() -> dict:
    conn = get_scrape_db()
    cursor = conn.execute("""
        SELECT url, content_hash, scraped_at
        FROM scraped_urls
        ORDER BY scraped_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    last_scrape = row[2] if row else "never"

    changes_detected = []
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (Educational Research Bot - MyCukai)"},
        timeout=15.0,
    )

    for url in CRITICAL_URLS:
        try:
            response = client.get(url)
            current_hash = hashlib.sha256(response.content).hexdigest()

            conn = get_scrape_db()
            stored = conn.execute(
                "SELECT content_hash FROM scraped_urls WHERE url = ?", (url,)
            ).fetchone()
            conn.close()

            if stored and stored[0] != current_hash:
                changes_detected.append({
                    "url": url,
                    "old_hash": stored[0],
                    "new_hash": current_hash,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            logger.warning("freshness_check_failed", url=url, error=str(e))

    client.close()

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "last_scrape": last_scrape,
        "changes_detected": len(changes_detected),
        "changed_urls": changes_detected,
        "status": "needs_update" if changes_detected else "fresh",
    }

    logger.info("freshness_report", status=report["status"], changes=len(changes_detected))
    return report


def trigger_update_if_needed():
    report = check_freshness()
    if report["status"] == "needs_update":
        logger.info("triggering_update", changes=report["changes_detected"])
        from scraper.lhdn_spider import run as run_lhdn
        from processor.pipeline import process_all
        from embedder.vector_store import embed_all_chunks

        run_lhdn()
        process_all()
        embed_all_chunks()
        return True
    return False


if __name__ == "__main__":
    report = check_freshness()
    print(json.dumps(report, indent=2))
