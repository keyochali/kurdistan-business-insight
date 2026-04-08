"""
Supabase REST API client for production database operations.
Uses PostgREST (the Supabase REST API) instead of direct PostgreSQL connections.
This works even when the DB is paused on the free tier.
"""

import json
import logging
from typing import Optional
from datetime import date, datetime

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzMTg2MywiZXhwIjoyMDg4NDA3ODYzfQ.NxlhFmuFlAwhXZlTDclGXEGUOepFOnHyCXjM6bEV0mc"


def _headers(prefer="return=representation"):
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _serialize(obj):
    """JSON-serialize dates and datetimes."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


class SupabaseDB:
    """REST-based database client for Supabase."""

    def __init__(self):
        self.url = SUPABASE_URL
        self.client = httpx.Client(timeout=30)

    def _post(self, table, data, upsert=False):
        prefer = "return=representation"
        if upsert:
            prefer += ",resolution=merge-duplicates"
        # Serialize all values
        clean = {k: _serialize(v) for k, v in data.items()}
        r = self.client.post(
            f"{self.url}/rest/v1/{table}",
            headers=_headers(prefer),
            json=clean,
        )
        if r.status_code >= 400:
            logger.error(f"Supabase POST {table}: {r.status_code} {r.text[:200]}")
            return None
        return r.json()

    def _get(self, table, params="", limit=1000):
        r = self.client.get(
            f"{self.url}/rest/v1/{table}?{params}&limit={limit}",
            headers=_headers(),
        )
        if r.status_code >= 400:
            logger.error(f"Supabase GET {table}: {r.status_code} {r.text[:200]}")
            return []
        return r.json()

    def _patch(self, table, params, data):
        clean = {k: _serialize(v) for k, v in data.items()}
        r = self.client.patch(
            f"{self.url}/rest/v1/{table}?{params}",
            headers=_headers(),
            json=clean,
        )
        if r.status_code >= 400:
            logger.error(f"Supabase PATCH {table}: {r.status_code} {r.text[:200]}")
            return None
        return r.json()

    def _delete(self, table, params):
        r = self.client.delete(
            f"{self.url}/rest/v1/{table}?{params}",
            headers=_headers(),
        )
        return r.status_code < 400

    # ── Table existence check ──
    def tables_exist(self):
        """Check if our tables exist in Supabase."""
        r = self.client.get(f"{self.url}/rest/v1/", headers=_headers())
        if r.status_code != 200:
            return False
        paths = [p.strip("/") for p in r.json().get("paths", {}).keys() if p != "/"]
        return "articles" in paths

    # ── Articles ──
    def get_articles(self, published_only=True):
        params = "is_published=eq.true&order=rank.asc" if published_only else "order=rank.asc"
        return self._get("articles", params)

    def get_article_by_slug(self, slug):
        rows = self._get("articles", f"slug=eq.{slug}&is_published=eq.true", limit=1)
        return rows[0] if rows else None

    def insert_article(self, data):
        return self._post("articles", data)

    def get_article_images(self, article_id):
        return self._get("article_images", f"article_id=eq.{article_id}")

    def insert_article_image(self, data):
        return self._post("article_images", data)

    # ── Source profiles ──
    def get_source_profiles(self):
        return self._get("source_profiles")

    def upsert_source_profile(self, data):
        return self._post("source_profiles", data, upsert=True)

    # ── Profiles & Companies ──
    def get_profiles(self):
        return self._get("linkedin_profiles", "order=name.asc")

    def get_companies(self):
        return self._get("linkedin_companies", "order=name.asc")

    # ── Categories ──
    def get_categories(self):
        articles = self.get_articles()
        counts = {}
        for a in articles:
            cat = a.get("category") or "Uncategorized"
            counts[cat] = counts.get(cat, 0) + 1
        return sorted(
            [{"category": k, "count": v} for k, v in counts.items()],
            key=lambda x: x["count"], reverse=True,
        )

    # ── Dates ──
    def get_available_dates(self):
        articles = self.get_articles()
        counts = {}
        for a in articles:
            d = a.get("publish_date")
            if d:
                counts[d] = counts.get(d, 0) + 1
        return sorted(
            [{"date": k, "count": v} for k, v in counts.items()],
            key=lambda x: x["date"], reverse=True,
        )


def sync_to_supabase():
    """
    One-time sync: push current data.json content to Supabase tables.
    Called from the pipeline after generating articles.
    """
    db = SupabaseDB()

    if not db.tables_exist():
        logger.warning("Supabase tables don't exist yet. Skipping sync.")
        return False

    try:
        with open("frontend/public/data.json") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("No data.json found for Supabase sync")
        return False

    # Sync articles
    for article in data.get("articles", []):
        # Clean up fields for Supabase
        article_data = {
            "slug": article["slug"],
            "headline": article["headline"],
            "subheadline": article.get("subheadline"),
            "summary": article.get("summary"),
            "body_html": article.get("body_html"),
            "body_markdown": article.get("body_markdown"),
            "category": article.get("category"),
            "tags": article.get("tags", []),
            "featured_image_url": article.get("featured_image_url"),
            "featured_image_local": article.get("featured_image_local"),
            "author_attribution": article.get("author_attribution"),
            "publish_date": article.get("publish_date"),
            "is_published": True,
            "reading_time_minutes": article.get("reading_time_minutes", 3),
            "rank": article.get("rank"),
        }
        db.insert_article(article_data)

    # Sync source profiles
    for source in data.get("sources", []):
        db.upsert_source_profile(source)

    logger.info(f"Synced {len(data.get('articles', []))} articles and {len(data.get('sources', []))} sources to Supabase")
    return True
