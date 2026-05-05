"""
Fix source profile avatars by re-scraping LinkedIn via Apify,
downloading fresh avatar images, and uploading to Supabase Storage.

LinkedIn CDN URLs expire and block hotlinking. This script:
1. Gets all source profiles from Supabase (with their LinkedIn URLs)
2. Scrapes minimal post data via Apify to get fresh avatar URLs
3. Downloads avatars immediately (before URLs expire)
4. Uploads to Supabase Storage (permanent)
5. Updates source_profiles.avatar_url in the database
"""

import json
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import httpx
from apify_client import ApifyClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('fix_avatars')

SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzMTg2MywiZXhwIjoyMDg4NDA3ODYzfQ.NxlhFmuFlAwhXZlTDclGXEGUOepFOnHyCXjM6bEV0mc"
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
ACTOR_ID = "harvestapi/linkedin-profile-posts"

client = httpx.Client(timeout=30)


def supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_source_profiles():
    """Get all source profiles that need avatars."""
    r = client.get(
        f"{SUPABASE_URL}/rest/v1/source_profiles?select=id,name,linkedin_url,avatar_url,type&limit=500",
        headers=supa_headers(),
    )
    return r.json() if r.status_code == 200 else []


def scrape_avatars(urls):
    """Use Apify to scrape LinkedIn posts and extract author avatars."""
    if not APIFY_TOKEN:
        logger.error("No APIFY_API_TOKEN set!")
        return {}

    apify = ApifyClient(APIFY_TOKEN)

    # Ensure trailing slashes
    urls = [u.rstrip("/") + "/" for u in urls]

    logger.info(f"Scraping {len(urls)} LinkedIn URLs via Apify (1 post each)...")

    # Just get 1 post per URL - we only need the author avatar
    run_input = {
        "targetUrls": urls,
        "maxPosts": 1,
        "postedLimit": "year",  # broad window to ensure we get at least 1 post
    }

    try:
        run = apify.actor(ACTOR_ID).call(run_input=run_input)
        items = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
        logger.info(f"Got {len(items)} results from Apify")
    except Exception as e:
        logger.error(f"Apify scrape failed: {e}")
        return {}

    # Extract avatars: map linkedin_url -> avatar_url
    avatars = {}
    for item in items:
        author = item.get("author", {})
        avatar = author.get("avatar", {})
        avatar_url = avatar.get("url") if isinstance(avatar, dict) else None
        name = author.get("name", "")
        linkedin_url = author.get("linkedinUrl", "")

        # Also try query.targetUrl for matching
        target_url = item.get("query", {}).get("targetUrl", "")

        if avatar_url and name:
            avatars[name] = {
                "avatar_url": avatar_url,
                "linkedin_url": linkedin_url,
                "target_url": target_url,
            }

    logger.info(f"Extracted {len(avatars)} unique avatars")
    return avatars


def download_and_upload(name, avatar_url):
    """Download avatar from LinkedIn and upload to Supabase Storage."""
    try:
        r = client.get(avatar_url, follow_redirects=True)
        if r.status_code != 200:
            logger.warning(f"  Download failed ({r.status_code}): {name}")
            return None

        ct = r.headers.get("content-type", "image/jpeg")
        ext = ".png" if "png" in ct else ".jpg"
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        storage_path = f"avatars/{slug}{ext}"

        upload = client.post(
            f"{SUPABASE_URL}/storage/v1/object/article-images/{storage_path}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": ct,
                "x-upsert": "true",
            },
            content=r.content,
        )

        if upload.status_code in (200, 201):
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/article-images/{storage_path}"
            return public_url
        else:
            logger.warning(f"  Upload failed ({upload.status_code}): {name}")
            return None
    except Exception as e:
        logger.warning(f"  Error for {name}: {e}")
        return None


def update_avatar(profile_id, avatar_url):
    """Update a source profile's avatar_url in Supabase."""
    r = client.patch(
        f"{SUPABASE_URL}/rest/v1/source_profiles?id=eq.{profile_id}",
        headers=supa_headers(),
        json={"avatar_url": avatar_url},
    )
    return r.status_code < 300


def main():
    logger.info("=== Fixing source profile avatars ===\n")

    # Step 1: Get profiles that need avatars
    profiles = get_source_profiles()
    needs_avatar = [p for p in profiles if not p.get("avatar_url") or "licdn.com" in (p.get("avatar_url") or "")]
    logger.info(f"Total profiles: {len(profiles)}, need avatars: {len(needs_avatar)}")

    if not needs_avatar:
        logger.info("All profiles have working avatars!")
        return

    # Step 2: Collect LinkedIn URLs to scrape
    urls_to_scrape = list(set(p["linkedin_url"] for p in needs_avatar if p.get("linkedin_url")))
    logger.info(f"Unique LinkedIn URLs to scrape: {len(urls_to_scrape)}")

    # Scrape in batches of 15
    all_avatars = {}
    batch_size = 15
    for i in range(0, len(urls_to_scrape), batch_size):
        batch = urls_to_scrape[i:i + batch_size]
        logger.info(f"\nBatch {i // batch_size + 1}/{(len(urls_to_scrape) + batch_size - 1) // batch_size}: scraping {len(batch)} URLs...")
        avatars = scrape_avatars(batch)
        all_avatars.update(avatars)

    logger.info(f"\nTotal avatars found: {len(all_avatars)}")

    # Step 3: Download and upload each avatar
    fixed = 0
    failed = 0
    for profile in needs_avatar:
        name = profile["name"]
        avatar_data = all_avatars.get(name)

        if not avatar_data:
            logger.info(f"  SKIP (no avatar found): {name}")
            failed += 1
            continue

        logger.info(f"  Downloading: {name}")
        supabase_url = download_and_upload(name, avatar_data["avatar_url"])

        if supabase_url:
            if update_avatar(profile["id"], supabase_url):
                logger.info(f"  OK: {name} -> {supabase_url}")
                fixed += 1
            else:
                failed += 1
        else:
            failed += 1

    logger.info(f"\n=== Done: {fixed} fixed, {failed} failed ===")


if __name__ == "__main__":
    main()
