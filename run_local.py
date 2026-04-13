"""
Local pipeline runner — your laptop is the computation engine,
Supabase is the database for everything.

Flow:
  1. Read profiles/companies from Supabase
  2. Scrape LinkedIn via Apify (or use cached posts from Supabase)
  3. Label, embed, select, deduplicate, write, edit articles (all local compute)
  4. Push everything back to Supabase (articles, images, memories, posts)
  5. Update data.json and push to GitHub so Vercel redeploys
"""

import json
import logging
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('data/pipeline.log', mode='w'),
        logging.StreamHandler(sys.stdout),
    ]
)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('apify_client').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)

logger = logging.getLogger('local_pipeline')

import httpx
from backend.config import settings
from backend.database.connection import init_db, SessionLocal
from backend.database.models import (
    PipelineRun, PipelineStatus, Article, LinkedInProfile, LinkedInCompany,
    RawPost, ProcessedPost, ArticleImage,
)
from backend.scraper.apify_client import LinkedInScraper
from backend.scraper.post_filter import filter_todays_posts
from backend.processing.labeler import PostLabeler
from backend.processing.embeddings import EmbeddingEngine
from backend.generation.selector import ArticleSelector
from backend.generation.writer import ArticleWriter
from backend.generation.editor import ArticleEditor
from backend.generation.publisher import ArticlePublisher
from backend.processing.memory import MemoryManager
from backend.processing.dedup import get_recent_headlines, deduplicate_selections, deduplicate_against_published

TIMEZONE = ZoneInfo(settings.timezone)
SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzMTg2MywiZXhwIjoyMDg4NDA3ODYzfQ.NxlhFmuFlAwhXZlTDclGXEGUOepFOnHyCXjM6bEV0mc"


def supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def supa_get(table, params="", limit=1000):
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}&limit={limit}", headers=supa_headers(), timeout=30)
    return r.json() if r.status_code == 200 else []


def supa_post(table, data):
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=supa_headers(), json=data, timeout=30)
    if r.status_code >= 400:
        logger.warning(f"Supabase POST {table} failed: {r.status_code} {r.text[:100]}")
        return None
    return r.json()


def supa_upsert(table, data):
    h = supa_headers()
    h["Prefer"] = "return=representation,resolution=merge-duplicates"
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, json=data, timeout=30)
    return r.json() if r.status_code < 400 else None


def supa_delete(table, params):
    r = httpx.delete(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=supa_headers(), timeout=30)
    return r.status_code < 400


def check_supabase():
    """Check if Supabase tables exist."""
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/articles?limit=1", headers=supa_headers(), timeout=5)
        return r.status_code == 200
    except:
        return False


def sync_profiles_from_supabase():
    """Pull profiles and companies from Supabase and write to local JSON files."""
    profiles = supa_get("linkedin_profiles", "is_active=eq.true&order=name.asc")
    companies = supa_get("linkedin_companies", "is_active=eq.true&order=name.asc")

    if profiles:
        with open("data/profiles.json", "w") as f:
            json.dump([{"name": p["name"], "url": p["linkedin_url"]} for p in profiles], f, indent=2)
        logger.info(f"Pulled {len(profiles)} profiles from Supabase")

    if companies:
        with open("data/companies.json", "w") as f:
            json.dump([{"name": c["name"], "url": c["linkedin_url"]} for c in companies], f, indent=2)
        logger.info(f"Pulled {len(companies)} companies from Supabase")

    return profiles, companies


def push_articles_to_supabase(db):
    """Push all published articles to Supabase."""
    articles = db.query(Article).filter(Article.is_published == True).all()
    logger.info(f"Pushing {len(articles)} articles to Supabase...")

    # Clear old articles from Supabase first
    supa_delete("article_images", "id=gt.0")
    supa_delete("articles", "id=gt.0")
    logger.info("Cleared old articles from Supabase")

    for article in articles:
        tags = article.tags
        if isinstance(tags, str):
            try: tags = json.loads(tags)
            except: tags = []

        # Clean localhost refs from body_html
        html = article.body_html or ""
        html = re.sub(r'<figure class="article-inline-image"[^>]*>.*?</figure>', '', html, flags=re.DOTALL)

        data = {
            "slug": article.slug,
            "headline": article.headline,
            "subheadline": article.subheadline,
            "summary": article.summary,
            "body_html": html,
            "body_markdown": article.body_markdown,
            "category": article.category,
            "tags": tags,
            "featured_image_url": article.featured_image_url,
            "featured_image_local": article.featured_image_local,
            "author_attribution": article.author_attribution,
            "publish_date": article.publish_date.isoformat() if article.publish_date else None,
            "is_published": True,
            "reading_time_minutes": article.reading_time_minutes,
            "rank": article.rank,
        }
        result = supa_upsert("articles", data)
        if result and isinstance(result, list) and len(result) > 0:
            new_id = result[0].get("id")
            # Push images for this article
            if new_id:
                images = db.query(ArticleImage).filter_by(article_id=article.id).all()
                for img in images:
                    supa_post("article_images", {
                        "article_id": new_id,
                        "image_url": img.image_url,
                        "local_path": img.local_path,
                        "is_featured": img.is_featured,
                    })

    logger.info("Articles pushed to Supabase")


def push_source_profiles_to_supabase():
    """Push source profiles to Supabase."""
    try:
        with open("data/source_profiles.json") as f:
            sources = json.load(f)
        for s in sources:
            supa_upsert("source_profiles", {
                "name": s["name"],
                "linkedin_url": s["linkedin_url"],
                "avatar_url": s["avatar_url"],
                "headline": s.get("headline", ""),
                "type": s.get("type", "profile"),
            })
        logger.info(f"Pushed {len(sources)} source profiles to Supabase")
    except FileNotFoundError:
        pass


def export_data_json(db):
    """Export data.json for the frontend (static fallback)."""
    articles = db.query(Article).filter(Article.is_published == True).order_by(Article.rank).all()

    items = []
    for r in articles:
        tags = r.tags
        if isinstance(tags, str):
            try: tags = json.loads(tags)
            except: tags = []
        html = r.body_html or ""
        html = re.sub(r'<figure class="article-inline-image"[^>]*>.*?</figure>', '', html, flags=re.DOTALL)

        images = []
        for img in db.query(ArticleImage).filter_by(article_id=r.id).all():
            images.append({"image_url": img.image_url, "local_path": img.local_path, "is_featured": img.is_featured})

        items.append({
            "id": r.id, "slug": r.slug, "headline": r.headline,
            "subheadline": r.subheadline, "summary": r.summary,
            "body_html": html, "body_markdown": r.body_markdown,
            "category": r.category, "tags": tags,
            "featured_image_url": r.featured_image_url,
            "featured_image_local": r.featured_image_local,
            "author_attribution": r.author_attribution,
            "publish_date": r.publish_date.isoformat() if r.publish_date else None,
            "is_published": True, "reading_time_minutes": r.reading_time_minutes,
            "rank": r.rank, "images": images,
        })

    profiles = [{"id": p.id, "name": p.name, "linkedin_url": p.linkedin_url, "is_active": p.is_active}
                for p in db.query(LinkedInProfile).all()]
    companies = [{"id": c.id, "name": c.name, "linkedin_url": c.linkedin_url, "is_active": c.is_active}
                 for c in db.query(LinkedInCompany).all()]
    sources = []
    try:
        with open("data/source_profiles.json") as f: sources = json.load(f)
    except: pass

    with open("frontend/public/data.json", "w") as f:
        json.dump({"articles": items, "sources": sources, "profiles": profiles, "companies": companies}, f)

    logger.info(f"Exported {len(items)} articles to data.json")


def push_to_github():
    """Commit and push data.json + SEO files to GitHub."""
    try:
        subprocess.run(["python", "generate_seo.py"], check=True, capture_output=True)
    except: pass

    try:
        subprocess.run(["git", "add", "frontend/public/data.json", "frontend/public/sitemap.xml",
                        "frontend/public/robots.txt", "frontend/public/meta.json",
                        "data/profiles.json", "data/companies.json"], check=True, capture_output=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", f"Update articles {date.today().isoformat()}"], check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "master"], check=True, capture_output=True, timeout=30)
            logger.info("Pushed updates to GitHub → Vercel will redeploy")
        else:
            logger.info("No changes to push")
    except Exception as e:
        logger.warning(f"Git push failed: {e}")


def main():
    init_db()
    today = datetime.now(TIMEZONE).date()
    use_supabase = check_supabase()

    logger.info(f"=== Local Pipeline Runner ===")
    logger.info(f"Date: {today}")
    logger.info(f"Supabase: {'connected' if use_supabase else 'using data.json fallback'}")

    # Pull profiles from Supabase if available
    if use_supabase:
        logger.info("Pulling profiles/companies from Supabase...")
        sync_profiles_from_supabase()

    db = SessionLocal()
    pipeline_run = PipelineRun(run_date=today, status=PipelineStatus.STARTED)
    db.add(pipeline_run)
    db.commit()

    try:
        # Memory system
        logger.info("Initializing memory system...")
        memory_mgr = MemoryManager(db)
        memory_mgr.ensure_all_memories_exist()

        # Check for cached posts
        from backend.database.models import RawPost
        existing_posts = db.query(RawPost).filter(RawPost.scrape_date >= today - timedelta(days=1)).all()

        if existing_posts and len(existing_posts) >= 10:
            logger.info(f"Using {len(existing_posts)} cached posts from local DB")
            stored_posts = existing_posts
        else:
            logger.info("Scraping LinkedIn posts...")
            pipeline_run.status = PipelineStatus.SCRAPING
            db.commit()

            scraper = LinkedInScraper()
            raw_data = scraper.scrape_all(max_posts=20)
            all_posts = raw_data["profile_posts"] + raw_data["company_posts"]
            logger.info(f"Scraped {len(all_posts)} posts")

            with open('data/raw_scrape.json', 'w') as f:
                json.dump(raw_data, f, default=str, indent=2)

            todays_posts = filter_todays_posts(all_posts, today, lookback_days=1)
            if len(todays_posts) < 20:
                logger.info(f"Only {len(todays_posts)} posts from last 1 day, trying 7 days...")
                todays_posts = filter_todays_posts(all_posts, today, lookback_days=7)

            if not todays_posts:
                logger.warning("No posts found!")
                return

            # Deduplicate posts by ID before storing
            seen_ids = set()
            unique_posts = []
            for post in todays_posts:
                pid = post.get("postId")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    unique_posts.append(post)
                elif not pid:
                    unique_posts.append(post)
            todays_posts = unique_posts
            logger.info(f"Deduplicated to {len(todays_posts)} unique posts")

            # Store posts
            stored_posts = []
            for post in todays_posts:
                author_name = post.get("authorName", "Unknown")
                target_url = post.get("targetUrl", "")
                profile = db.query(LinkedInProfile).filter(
                    LinkedInProfile.linkedin_url.contains(target_url.rstrip("/").split("/")[-1])
                ).first() if "/in/" in target_url else None
                company = db.query(LinkedInCompany).filter(
                    LinkedInCompany.linkedin_url.contains(target_url.rstrip("/").split("/")[-1])
                ).first() if "/company/" in target_url else None

                posted_at_val = post.get("_parsed_date")
                if isinstance(posted_at_val, str):
                    try: posted_at_val = datetime.fromisoformat(posted_at_val)
                    except: posted_at_val = None

                # Skip duplicates
                post_id = post.get("postId")
                if post_id and db.query(RawPost).filter_by(linkedin_post_id=post_id).first():
                    continue

                raw_post = RawPost(
                    profile_id=profile.id if profile else None,
                    company_id=company.id if company else None,
                    linkedin_post_id=post_id,
                    post_url=post.get("postUrl"),
                    author_name=author_name,
                    author_headline=post.get("authorHeadline", ""),
                    author_profile_url=post.get("authorProfileUrl", ""),
                    content_text=post.get("text", ""),
                    post_type=post.get("postType", "post"),
                    posted_at=posted_at_val,
                    scrape_date=today,
                    likes_count=post.get("likesCount", 0),
                    comments_count=post.get("commentsCount", 0),
                    shares_count=post.get("sharesCount", 0),
                    image_urls=post.get("images", []),
                    raw_data=post.get("_raw"),
                    pipeline_run_id=pipeline_run.id,
                )
                db.add(raw_post)
                stored_posts.append(raw_post)
            db.commit()

        pipeline_run.posts_found = len(stored_posts)
        logger.info(f"Working with {len(stored_posts)} posts")

        # Label
        logger.info("Labeling posts...")
        pipeline_run.status = PipelineStatus.PROCESSING
        db.commit()
        labeler = PostLabeler()
        labeler.set_memory_context_fn(memory_mgr.get_context_for_post)
        post_dicts = [{"id": rp.id, "author_name": rp.author_name, "author_headline": rp.author_headline,
                       "content_text": rp.content_text, "post_type": rp.post_type,
                       "likes_count": rp.likes_count, "comments_count": rp.comments_count,
                       "shares_count": rp.shares_count, "image_urls": rp.image_urls, "post_url": rp.post_url}
                      for rp in stored_posts]
        labeled_posts = labeler.label_batch(post_dicts)

        # Embed
        logger.info("Generating embeddings...")
        embedder = EmbeddingEngine()
        texts, valid_labeled = [], []
        for lp in labeled_posts:
            if lp["labels"] is None: continue
            texts.append(embedder.build_post_text(lp["post"], lp["labels"]))
            valid_labeled.append(lp)
        embeddings = embedder.generate_batch_embeddings(texts)
        cluster_ids = embedder.cluster_posts(embeddings) if embeddings else []
        for i, lp in enumerate(valid_labeled):
            if i < len(embeddings): lp["embedding"] = embeddings[i]
            if i < len(cluster_ids): lp["cluster_id"] = cluster_ids[i]

        # Store processed posts
        for i, lp in enumerate(valid_labeled):
            labels = lp.get("labels")
            if not labels: continue
            post_id = lp["post"].get("id")
            if not post_id: continue
            db.add(ProcessedPost(
                raw_post_id=post_id, summary=labels.get("summary"), category=labels.get("category"),
                tags=labels.get("tags", []), sentiment=labels.get("sentiment"),
                key_entities=labels.get("key_entities", []), industry_sector=labels.get("industry_sector"),
                newsworthiness_score=labels.get("newsworthiness_score", 0),
                embedding=embeddings[i] if i < len(embeddings) else None,
                cluster_id=cluster_ids[i] if i < len(cluster_ids) else None,
            ))
        db.commit()

        # Select
        logger.info("Selecting articles...")
        pipeline_run.status = PipelineStatus.GENERATING
        db.commit()
        selector = ArticleSelector()
        selector.set_authority_scores(memory_mgr.get_all_authority_scores())
        recent = get_recent_headlines(db, days=7)
        if recent: selector.set_recent_headlines(recent)
        selections = selector.select_articles(valid_labeled, article_count=min(20, len(valid_labeled)))

        # Dedup
        logger.info("Deduplicating...")
        selections = deduplicate_selections(selections, valid_labeled, embedder)
        if recent: selections = deduplicate_against_published(selections, db, embedder, days=7)
        logger.info(f"After dedup: {len(selections)} unique selections")

        # If dedup removed too many, select more from remaining candidates
        target = 20
        if len(selections) < target:
            used_ids = set()
            for s in selections:
                used_ids.update(s.get("post_ids", []))
            remaining = [lp for i, lp in enumerate(valid_labeled) if i not in used_ids]
            if remaining:
                extra = selector.select_articles(remaining, article_count=target - len(selections))
                extra = deduplicate_selections(extra, remaining, embedder)
                selections.extend(extra[:target - len(selections)])
                logger.info(f"Backfilled to {len(selections)} selections")

        # Write
        logger.info("Writing articles...")
        writer = ArticleWriter()
        writer.set_memory_context_fn(memory_mgr.get_context_for_post)
        articles = writer.write_batch(selections)

        # Post-write dedup: check written articles for similarity by headline
        logger.info("Post-write dedup on headlines...")
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim
        import numpy as np
        headline_texts = [a.get("headline", "") for a in articles]
        if len(headline_texts) > 1:
            h_embeddings = embedder.generate_batch_embeddings(headline_texts)
            sim = cos_sim(np.array(h_embeddings))
            to_remove = set()
            for i in range(len(articles)):
                if i in to_remove: continue
                for j in range(i+1, len(articles)):
                    if j in to_remove: continue
                    if sim[i][j] > 0.6:
                        to_remove.add(j)
                        logger.info(f"Post-write dedup: removing \"{articles[j].get('headline','')[:50]}\" (sim={sim[i][j]:.2f})")
            if to_remove:
                articles = [a for idx, a in enumerate(articles) if idx not in to_remove]
                logger.info(f"After post-write dedup: {len(articles)} articles")

        # Edit
        logger.info("Editing articles...")
        from backend.generation.editor import ArticleEditor
        edited = ArticleEditor().edit_batch(articles)

        # Publish
        logger.info("Publishing...")
        publisher = ArticlePublisher(db)
        published = publisher.publish_batch(edited, today, pipeline_run.id)
        logger.info(f"Published {len(published)} articles")

        # Generate images for articles without photos
        logger.info("Generating images for articles without photos...")
        from backend.generation.image_gen import generate_article_image, download_and_upload_image

        # Load source profiles for color extraction
        source_profiles = []
        try:
            with open("data/source_profiles.json") as f:
                source_profiles = json.load(f)
        except: pass

        def match_sources(attr):
            if not attr: return []
            attr_lower = attr.lower()
            return [s for s in source_profiles if s.get("name") and s["name"].lower() in attr_lower]

        no_image_count = 0
        for article in published:
            if not article.featured_image_url:
                article_sources = match_sources(article.author_attribution)
                img_url = generate_article_image(
                    headline=article.headline,
                    category=article.category or "Business",
                    summary=article.summary or "",
                    sources=article_sources,
                )
                if img_url:
                    # Download and get permanent URL
                    permanent_url = download_and_upload_image(img_url, article.slug)
                    if permanent_url:
                        article.featured_image_url = permanent_url
                        no_image_count += 1
        if no_image_count:
            db.commit()
            logger.info(f"Generated {no_image_count} images for articles without photos")
        else:
            logger.info("All articles already have images")

        # Update memories
        logger.info("Updating memories...")
        memory_mgr.update_daily_memories(today)

        pipeline_run.status = PipelineStatus.COMPLETED
        pipeline_run.articles_generated = len(published)
        pipeline_run.completed_at = datetime.utcnow()
        db.commit()

        # ── Extract source profiles from raw scrape ──
        logger.info("Updating source profiles...")
        try:
            with open("data/raw_scrape.json") as f:
                raw_data = json.load(f)
            existing_sources = {}
            try:
                with open("data/source_profiles.json") as f:
                    for s in json.load(f):
                        existing_sources[s["name"]] = s
            except FileNotFoundError:
                pass
            for post in raw_data.get("company_posts", []) + raw_data.get("profile_posts", []):
                raw = post.get("_raw", {})
                author = raw.get("author", {})
                name = author.get("name", "")
                if not name or name in existing_sources:
                    continue
                avatar = author.get("avatar", {})
                pic_url = avatar.get("url", "") if isinstance(avatar, dict) else ""
                url = author.get("linkedinUrl", "").replace("/posts", "").rstrip("/")
                existing_sources[name] = {
                    "name": name, "linkedin_url": url, "avatar_url": pic_url,
                    "headline": author.get("info", ""), "type": author.get("type", "profile"),
                }
            with open("data/source_profiles.json", "w") as f:
                json.dump(list(existing_sources.values()), f, indent=2)
            logger.info(f"Source profiles: {len(existing_sources)} total")
        except Exception as e:
            logger.warning(f"Source profile extraction failed: {e}")

        # ── Push to Supabase ──
        if use_supabase:
            logger.info("Syncing to Supabase...")
            push_articles_to_supabase(db)
            push_source_profiles_to_supabase()

        # ── Export data.json and push to GitHub ──
        logger.info("Exporting data.json...")
        export_data_json(db)
        push_to_github()

        logger.info(f"=== DONE: {len(published)} articles published ===")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        pipeline_run.status = PipelineStatus.FAILED
        pipeline_run.error_message = str(e)
        pipeline_run.completed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
