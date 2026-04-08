"""
APScheduler-based scheduler that triggers the daily pipeline.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.config import settings
from backend.pipeline import DailyPipeline

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def run_daily_pipeline():
    """Scheduled job: run the daily pipeline."""
    logger.info("=== Scheduled daily pipeline starting ===")
    pipeline = DailyPipeline()
    summary = pipeline.run()
    logger.info(f"=== Scheduled pipeline completed: {summary} ===")


def start_scheduler():
    """Start the background scheduler."""
    tz = ZoneInfo(settings.timezone)

    scheduler.add_job(
        run_daily_pipeline,
        trigger=CronTrigger(
            hour=settings.scrape_hour,
            minute=settings.scrape_minute,
            timezone=tz,
        ),
        id="daily_pipeline",
        name="Daily LinkedIn News Pipeline",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started. Pipeline runs daily at "
        f"{settings.scrape_hour:02d}:{settings.scrape_minute:02d} ({settings.timezone})"
    )


def stop_scheduler():
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
