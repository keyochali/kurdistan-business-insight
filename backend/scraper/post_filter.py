"""
Filters scraped LinkedIn posts to only include those published today.
Handles the normalized post format from our scraper.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from backend.config import settings

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo(settings.timezone)


def parse_post_date(post: dict) -> Optional[datetime]:
    """
    Extract and parse the publication date from a normalized post.
    Our scraper normalizes to: postedDateTimestamp (ms), postedDate (ISO string), postedAgo (relative).
    """
    # 1. Try millisecond timestamp (most reliable)
    ts = post.get("postedDateTimestamp")
    if isinstance(ts, (int, float)) and ts > 0:
        if ts > 1e12:
            ts = ts / 1000  # milliseconds to seconds
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TIMEZONE)

    # 2. Try ISO date string
    date_str = post.get("postedDate")
    if isinstance(date_str, str) and date_str:
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(TIMEZONE)
            except ValueError:
                continue

    # 3. Try relative date like "5d", "2h", "1w"
    ago = post.get("postedAgo", "")
    if ago:
        return _parse_relative_date(ago)

    logger.warning(f"Could not parse date from post: {post.get('postUrl', 'unknown')}")
    return None


def _parse_relative_date(relative: str) -> Optional[datetime]:
    """Parse relative dates like '2h', '1d', '3w' from LinkedIn."""
    now = datetime.now(TIMEZONE)
    relative = relative.strip()

    try:
        if relative.endswith("h"):
            return now - timedelta(hours=int(relative[:-1]))
        elif relative.endswith("d"):
            return now - timedelta(days=int(relative[:-1]))
        elif relative.endswith("w"):
            return now - timedelta(weeks=int(relative[:-1]))
        elif relative.endswith("mo"):
            return now - timedelta(days=int(relative[:-2]) * 30)
        elif relative.endswith("m"):
            return now - timedelta(minutes=int(relative[:-1]))
    except ValueError:
        pass

    return None


def filter_todays_posts(posts: list[dict], target_date: Optional[date] = None, lookback_days: int = 1) -> list[dict]:
    """
    Filter posts to only include those published on the target date or within lookback_days before it.
    Defaults to today in the configured timezone with 1 day lookback.
    """
    if target_date is None:
        target_date = datetime.now(TIMEZONE).date()

    earliest_date = target_date - timedelta(days=lookback_days)
    todays_posts = []

    for post in posts:
        post_dt = parse_post_date(post)
        if post_dt is None:
            logger.debug(f"Skipping post with unparseable date: {post.get('postUrl', 'unknown')}")
            continue

        post_date = post_dt.date()
        if earliest_date <= post_date <= target_date:
            post["_parsed_date"] = post_dt
            todays_posts.append(post)
        else:
            logger.debug(
                f"Skipping post from {post_date} (range: {earliest_date} to {target_date}): "
                f"{post.get('postUrl', 'unknown')}"
            )

    logger.info(f"Filtered {len(todays_posts)} recent posts from {len(posts)} total (range: {earliest_date} to {target_date})")
    return todays_posts


def extract_images_from_post(post: dict) -> list[str]:
    """Extract all image URLs from a normalized post."""
    images = post.get("images", [])
    if isinstance(images, list):
        return [u for u in images if isinstance(u, str) and u]
    return []
