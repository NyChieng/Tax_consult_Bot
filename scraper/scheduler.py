from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog

from scraper.lhdn_spider import run as run_lhdn
from scraper.gazette_spider import run as run_gazette
from scraper.sst_spider import run as run_sst
from scraper.big4_spider import run as run_big4
from scraper.news_monitor import run as run_news

logger = structlog.get_logger()


def create_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()

    # LHDN: Daily at 2am MYT (UTC+8 = 6pm UTC previous day)
    scheduler.add_job(
        run_lhdn,
        CronTrigger(hour=18, minute=0),  # 2am MYT
        id="lhdn_daily",
        name="LHDN Daily Scrape",
    )

    # Federal Gazette: Weekly Monday at 3am MYT
    scheduler.add_job(
        run_gazette,
        CronTrigger(day_of_week="mon", hour=19, minute=0),
        id="gazette_weekly",
        name="Gazette Weekly Scrape",
    )

    # SST Portal: Daily at 4am MYT
    scheduler.add_job(
        run_sst,
        CronTrigger(hour=20, minute=0),
        id="sst_daily",
        name="SST Daily Scrape",
    )

    # Big 4 Tax Alerts: Daily at 6am MYT
    scheduler.add_job(
        run_big4,
        CronTrigger(hour=22, minute=0),
        id="big4_daily",
        name="Big4 Daily Scrape",
    )

    # News: Every 6 hours
    scheduler.add_job(
        run_news,
        CronTrigger(hour="*/6"),
        id="news_6hourly",
        name="News Monitor",
    )

    return scheduler


def main():
    logger.info("starting_scrape_scheduler")
    scheduler = create_scheduler()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler_shutdown")


if __name__ == "__main__":
    main()
