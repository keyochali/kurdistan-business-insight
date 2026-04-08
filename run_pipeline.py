"""Standalone pipeline runner script."""
import json
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Configure logging - less verbose
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('data/pipeline.log', mode='w'),
        logging.StreamHandler(sys.stdout),
    ]
)
# Suppress noisy loggers
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('apify_client').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)

logger = logging.getLogger('pipeline_runner')

from backend.config import settings
from backend.database.connection import init_db, SessionLocal
from backend.database.models import PipelineRun, PipelineStatus, Article
from backend.scraper.apify_client import LinkedInScraper
from backend.scraper.post_filter import filter_todays_posts, parse_post_date
from backend.processing.labeler import PostLabeler
from backend.processing.embeddings import EmbeddingEngine
from backend.generation.selector import ArticleSelector
from backend.generation.writer import ArticleWriter
from backend.generation.editor import ArticleEditor
from backend.generation.publisher import ArticlePublisher
from backend.processing.memory import MemoryManager
from backend.processing.dedup import get_recent_headlines, deduplicate_selections, deduplicate_against_published

TIMEZONE = ZoneInfo(settings.timezone)


def main():
    init_db()
    today = datetime.now(TIMEZONE).date()

    db = SessionLocal()
    pipeline_run = PipelineRun(run_date=today, status=PipelineStatus.STARTED)
    db.add(pipeline_run)
    db.commit()

    try:
        # ── Step 0: Initialize memory system ──
        logger.info("STEP 0: Initializing memory system...")
        memory_mgr = MemoryManager(db)
        memory_mgr.ensure_all_memories_exist()

        # ── Step 1: Get posts (from DB cache or fresh scrape) ──
        from backend.database.models import LinkedInProfile, LinkedInCompany, RawPost
        pipeline_run.status = PipelineStatus.SCRAPING
        db.commit()

        # Check if we already have scraped posts in the DB (from today or recent)
        existing_posts = db.query(RawPost).filter(
            RawPost.scrape_date >= today - timedelta(days=1)
        ).all()

        if existing_posts and len(existing_posts) >= 10:
            logger.info(f"STEP 1: Using {len(existing_posts)} cached posts from DB (already scraped)")
            stored_posts = existing_posts
            pipeline_run.posts_found = len(stored_posts)
            pipeline_run.posts_today = len(stored_posts)
            db.commit()
        else:
            logger.info("STEP 1: Scraping LinkedIn posts (no recent cache)...")

            scraper = LinkedInScraper()
            raw_data = scraper.scrape_all(max_posts=20)
            all_posts = raw_data["profile_posts"] + raw_data["company_posts"]
            logger.info(f"Scraped {len(all_posts)} total posts")
            pipeline_run.posts_found = len(all_posts)

            with open('data/raw_scrape.json', 'w') as f:
                json.dump(raw_data, f, default=str, indent=2)

            # Filter recent posts
            logger.info("STEP 2: Filtering recent posts...")
            todays_posts = filter_todays_posts(all_posts, today, lookback_days=7)
            if len(todays_posts) < 20:
                logger.info(f"Only {len(todays_posts)} posts from last 7 days, trying last 30 days...")
                todays_posts = filter_todays_posts(all_posts, today, lookback_days=30)

            logger.info(f"Filtered to {len(todays_posts)} recent posts")
            pipeline_run.posts_today = len(todays_posts)
            db.commit()

            if not todays_posts:
                logger.warning("No posts found! Aborting.")
                pipeline_run.status = PipelineStatus.COMPLETED
                pipeline_run.completed_at = datetime.utcnow()
                db.commit()
                return

            # Store raw posts
            logger.info("STEP 3: Storing raw posts...")
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
                    try:
                        posted_at_val = datetime.fromisoformat(posted_at_val)
                    except (ValueError, TypeError):
                        posted_at_val = None

                raw_post = RawPost(
                    profile_id=profile.id if profile else None,
                    company_id=company.id if company else None,
                    linkedin_post_id=post.get("postId"),
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
            logger.info(f"Stored {len(stored_posts)} raw posts")

        # ── Step 4: Label and categorize ──
        logger.info("STEP 4: AI labeling and categorization...")
        pipeline_run.status = PipelineStatus.PROCESSING
        db.commit()

        labeler = PostLabeler()
        labeler.set_memory_context_fn(memory_mgr.get_context_for_post)
        post_dicts = []
        for rp in stored_posts:
            post_dicts.append({
                "id": rp.id,
                "author_name": rp.author_name,
                "author_headline": rp.author_headline,
                "content_text": rp.content_text,
                "post_type": rp.post_type,
                "likes_count": rp.likes_count,
                "comments_count": rp.comments_count,
                "shares_count": rp.shares_count,
                "image_urls": rp.image_urls,
                "post_url": rp.post_url,
            })

        labeled_posts = labeler.label_batch(post_dicts)
        valid_count = len([lp for lp in labeled_posts if lp["labels"]])
        logger.info(f"Successfully labeled {valid_count}/{len(labeled_posts)} posts")

        # ── Step 5: Generate embeddings ──
        logger.info("STEP 5: Generating embeddings...")
        embedder = EmbeddingEngine()
        texts = []
        valid_labeled = []
        for lp in labeled_posts:
            if lp["labels"] is None:
                continue
            text = embedder.build_post_text(lp["post"], lp["labels"])
            texts.append(text)
            valid_labeled.append(lp)

        embeddings = embedder.generate_batch_embeddings(texts)
        cluster_ids = embedder.cluster_posts(embeddings) if embeddings else []

        for i, lp in enumerate(valid_labeled):
            if i < len(embeddings):
                lp["embedding"] = embeddings[i]
            if i < len(cluster_ids):
                lp["cluster_id"] = cluster_ids[i]

        # Store processed posts
        from backend.database.models import ProcessedPost
        for i, lp in enumerate(valid_labeled):
            labels = lp.get("labels")
            if labels is None:
                continue
            post_id = lp["post"].get("id")
            if post_id is None:
                continue
            processed = ProcessedPost(
                raw_post_id=post_id,
                summary=labels.get("summary"),
                category=labels.get("category"),
                tags=labels.get("tags", []),
                sentiment=labels.get("sentiment"),
                key_entities=labels.get("key_entities", []),
                industry_sector=labels.get("industry_sector"),
                newsworthiness_score=labels.get("newsworthiness_score", 0),
                embedding=embeddings[i] if i < len(embeddings) else None,
                cluster_id=cluster_ids[i] if i < len(cluster_ids) else None,
            )
            db.add(processed)
        db.commit()
        logger.info(f"Stored {len(valid_labeled)} processed posts")

        # ── Step 6: Select top articles ──
        logger.info("STEP 6: Selecting top articles...")
        pipeline_run.status = PipelineStatus.GENERATING
        db.commit()

        selector = ArticleSelector()
        selector.set_authority_scores(memory_mgr.get_all_authority_scores())

        # Feed recently published headlines so AI avoids repeating stories
        recent_headlines = get_recent_headlines(db, days=7)
        if recent_headlines:
            selector.set_recent_headlines(recent_headlines)
            logger.info(f"Loaded {len(recent_headlines)} recent headlines for dedup")

        target_count = min(20, len(valid_labeled))
        selections = selector.select_articles(valid_labeled, article_count=target_count)
        logger.info(f"AI selected {len(selections)} articles")

        # ── Step 6b: Deduplicate selections ──
        logger.info("STEP 6b: Deduplicating selections...")

        # Intra-batch dedup (remove articles too similar to each other)
        selections = deduplicate_selections(selections, valid_labeled, embedder)
        logger.info(f"After intra-batch dedup: {len(selections)} articles")

        # Cross-day dedup (remove articles too similar to recently published)
        if recent_headlines:
            selections = deduplicate_against_published(selections, db, embedder, days=7)
            logger.info(f"After cross-day dedup: {len(selections)} articles")

        logger.info(f"Final selection: {len(selections)} unique articles")

        # ── Step 7: Write articles ──
        logger.info("STEP 7: Writing articles...")
        writer = ArticleWriter()
        writer.set_memory_context_fn(memory_mgr.get_context_for_post)
        articles = writer.write_batch(selections)
        logger.info(f"Wrote {len(articles)} articles")

        # ── Step 8: Edit articles ──
        logger.info("STEP 8: Editing articles...")
        editor = ArticleEditor()
        edited_articles = editor.edit_batch(articles)
        logger.info(f"Edited {len(edited_articles)} articles")

        # ── Step 9: Publish ──
        logger.info("STEP 9: Publishing articles...")
        publisher = ArticlePublisher(db)
        published = publisher.publish_batch(edited_articles, today, pipeline_run.id)
        logger.info(f"Published {len(published)} articles")

        # ── Step 10: Update daily memories ──
        logger.info("STEP 10: Updating daily memories from posts...")
        memories_updated = memory_mgr.update_daily_memories(today)
        logger.info(f"Updated {memories_updated} profile memories")

        # ── Done ──
        pipeline_run.status = PipelineStatus.COMPLETED
        pipeline_run.articles_generated = len(published)
        pipeline_run.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"=== PIPELINE COMPLETE: {len(published)} articles published ===")

        # Write summary
        summary = {
            "date": today.isoformat(),
            "posts_in_db": len(stored_posts),
            "posts_labeled": valid_count,
            "articles_selected": len(selections),
            "articles_written": len(articles),
            "articles_edited": len(edited_articles),
            "articles_published": len(published),
        }
        with open('data/pipeline_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        print(json.dumps(summary, indent=2))

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
