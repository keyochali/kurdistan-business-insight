"""
LinkedIn scraper using Apify's harvestapi/linkedin-profile-posts actor.
Scrapes posts from tracked LinkedIn profiles and companies.
"""

import json
import logging
from typing import Optional

from apify_client import ApifyClient

from backend.config import settings

logger = logging.getLogger(__name__)

ACTOR_ID = "harvestapi/linkedin-profile-posts"


class LinkedInScraper:
    """Handles all LinkedIn scraping via Apify actors."""

    def __init__(self):
        self.client = ApifyClient(settings.apify_api_token)

    def _load_profiles(self) -> list[dict]:
        path = settings.data_dir / "profiles.json"
        with open(path, "r") as f:
            return json.load(f)

    def _load_companies(self) -> list[dict]:
        path = settings.data_dir / "companies.json"
        with open(path, "r") as f:
            return json.load(f)

    def _ensure_trailing_slash(self, url: str) -> str:
        """Actor requires trailing slash on URLs."""
        return url.rstrip("/") + "/"

    def scrape_posts(
        self,
        urls: list[str],
        max_posts: int = 10,
        posted_limit: str = "24h",
    ) -> list[dict]:
        """
        Scrape recent posts from LinkedIn profiles/companies using Apify.
        """
        # Ensure trailing slashes on all URLs
        urls = [self._ensure_trailing_slash(u) for u in urls]
        logger.info(f"Scraping {len(urls)} LinkedIn URLs (limit: {posted_limit})...")

        run_input = {
            "targetUrls": urls,
            "maxPosts": max_posts,
            "postedLimit": posted_limit,
        }

        try:
            run = self.client.actor(ACTOR_ID).call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            logger.info(f"Scraped {len(items)} posts from {len(urls)} URLs")
            return items
        except Exception as e:
            logger.error(f"Error scraping: {e}")
            raise

    def normalize_post(self, raw: dict) -> dict:
        """
        Normalize an Apify post into a flat structure for the pipeline.
        Maps the nested actor output to our expected format.
        """
        author = raw.get("author", {})
        posted_at = raw.get("postedAt", {})
        engagement = raw.get("engagement", {})
        images = raw.get("postImages", [])

        return {
            "postId": raw.get("id"),
            "postUrl": raw.get("linkedinUrl"),
            "text": raw.get("content", ""),
            "authorName": author.get("name", "Unknown"),
            "authorHeadline": author.get("info", ""),
            "authorProfileUrl": author.get("linkedinUrl", ""),
            "authorType": author.get("type", "profile"),
            "postedDateTimestamp": posted_at.get("timestamp"),
            "postedDate": posted_at.get("date"),
            "postedAgo": posted_at.get("postedAgoShort", ""),
            "likesCount": engagement.get("likes", 0),
            "commentsCount": engagement.get("comments", 0),
            "sharesCount": engagement.get("shares", 0),
            "images": [img.get("url") for img in images if img.get("url")],
            "postType": raw.get("type", "post"),
            "targetUrl": raw.get("query", {}).get("targetUrl", ""),
            "_raw": raw,
        }

    def scrape_all(self, max_posts: int = 10) -> dict:
        """
        Scrape all tracked profiles and companies.
        Returns dict with normalized posts.
        """
        profiles = self._load_profiles()
        companies = self._load_companies()

        profile_urls = [p["url"] for p in profiles]
        company_urls = [c["url"] for c in companies]

        result = {
            "profile_posts": [],
            "company_posts": [],
            "profiles_metadata": {self._ensure_trailing_slash(p["url"]): p["name"] for p in profiles},
            "companies_metadata": {self._ensure_trailing_slash(c["url"]): c["name"] for c in companies},
        }

        # Scrape all URLs in batches
        all_urls = profile_urls + company_urls
        batch_size = 10
        for i in range(0, len(all_urls), batch_size):
            batch = all_urls[i : i + batch_size]
            try:
                raw_posts = self.scrape_posts(batch, max_posts=max_posts, posted_limit="week")
            except Exception as e:
                logger.error(f"Batch {i // batch_size + 1} failed: {e}")
                continue

            for raw in raw_posts:
                normalized = self.normalize_post(raw)
                target = normalized.get("targetUrl", "")
                if "/company/" in target:
                    result["company_posts"].append(normalized)
                else:
                    result["profile_posts"].append(normalized)

        logger.info(
            f"Total scraped: {len(result['profile_posts'])} profile posts, "
            f"{len(result['company_posts'])} company posts"
        )
        return result
