"""
Main daily pipeline orchestrator.
Coordinates scraping -> processing -> selection -> writing -> editing -> publishing.
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.connection import SessionLocal
from backend.database.models import (
    LinkedInProfile, LinkedInCompany, RawPost, ProcessedPost,
    PipelineRun, PipelineStatus,
)
from backend.scraper.apify_client import LinkedInScraper
from backend.scraper.post_filter import filter_todays_posts, extract_images_from_post
from backend.processing.labeler import PostLabeler
from backend.processing.embeddings import EmbeddingEngine
from backend.generation.selector import ArticleSelector
from backend.generation.writer import ArticleWriter
from backend.generation.editor import ArticleEditor
from backend.generation.publisher import ArticlePublisher

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo(settings.timezone)


class DailyPipeline:
    """Orchestrates the entire daily news generation pipeline."""

    def __init__(self):
        self.scraper = LinkedInScraper()
        self.labeler = PostLabeler()
        self.embedder = EmbeddingEngine()
        self.selector = ArticleSelector()
        self.writer = ArticleWriter()
        self.editor = ArticleEditor()

    def run(self, target_date: date | None = None) -> dict:
        """
        Execute the full pipeline for a given date.
        Returns a summary dict with stats and any errors.
        """
        if target_date is None:
            target_date = datetime.now(TIMEZONE).date()

        db = SessionLocal()
        pipeline_run = PipelineRun(
            run_date=target_date,
            status=PipelineStatus.STARTED,
        )
        db.add(pipeline_run)
        db.commit()

        summary = {
            "date": target_date.isoformat(),
            "pipeline_run_id": pipeline_run.id,
            "status": "started",
            "posts_scraped": 0,
            "posts_today": 0,
            "posts_processed": 0,
            "articles_selected": 0,
            "articles_written": 0,
            "articles_published": 0,
            "errors": [],
        }

        try:
            # ── Step 1: Scrape ──
            logger.info(f"=== STEP 1: Scraping LinkedIn posts for {target_date} ===")
            pipeline_run.status = PipelineStatus.SCRAPING
            db.commit()

            raw_data = self.scraper.scrape_all(max_posts=20)
            all_posts = raw_data["profile_posts"] + raw_data["company_posts"]
            summary["posts_scraped"] = len(all_posts)
            pipeline_run.posts_found = len(all_posts)

            # ── Step 2: Filter today's posts ──
            logger.info("=== STEP 2: Filtering today's posts ===")
            todays_posts = filter_todays_posts(all_posts, target_date, lookback_days=1)
            summary["posts_today"] = len(todays_posts)
            pipeline_run.posts_today = len(todays_posts)
            db.commit()

            if not todays_posts:
                logger.warning("No posts found for today. Pipeline complete.")
                pipeline_run.status = PipelineStatus.COMPLETED
                pipeline_run.completed_at = datetime.utcnow()
                db.commit()
                summary["status"] = "completed_no_posts"
                return summary

            # ── Step 3: Store raw posts ──
            logger.info("=== STEP 3: Storing raw posts ===")
            stored_posts = self._store_raw_posts(db, todays_posts, raw_data, target_date, pipeline_run.id)

            # ── Step 4: Label and categorize ──
            logger.info("=== STEP 4: AI labeling and categorization ===")
            pipeline_run.status = PipelineStatus.PROCESSING
            db.commit()

            post_dicts = self._posts_to_dicts(stored_posts, todays_posts)
            labeled_posts = self.labeler.label_batch(post_dicts)
            summary["posts_processed"] = len([lp for lp in labeled_posts if lp["labels"]])

            # ── Step 5: Generate embeddings and cluster ──
            logger.info("=== STEP 5: Generating embeddings ===")
            texts = []
            valid_labeled = []
            for lp in labeled_posts:
                if lp["labels"] is None:
                    continue
                text = self.embedder.build_post_text(lp["post"], lp["labels"])
                texts.append(text)
                valid_labeled.append(lp)

            embeddings = self.embedder.generate_batch_embeddings(texts)
            cluster_ids = self.embedder.cluster_posts(embeddings) if embeddings else []

            for i, lp in enumerate(valid_labeled):
                if i < len(embeddings):
                    lp["embedding"] = embeddings[i]
                if i < len(cluster_ids):
                    lp["cluster_id"] = cluster_ids[i]

            # Store processed posts
            self._store_processed_posts(db, valid_labeled, embeddings, cluster_ids)

            # ── Step 6: Select top articles ──
            logger.info("=== STEP 6: Selecting top articles ===")
            pipeline_run.status = PipelineStatus.GENERATING
            db.commit()

            selections = self.selector.select_articles(valid_labeled)
            summary["articles_selected"] = len(selections)

            # ── Step 7: Write articles ──
            logger.info("=== STEP 7: Writing articles ===")
            articles = self.writer.write_batch(selections)
            summary["articles_written"] = len(articles)

            # ── Step 8: Edit and review ──
            logger.info("=== STEP 8: Editing and reviewing articles ===")
            edited_articles = self.editor.edit_batch(articles)

            # ── Step 9: Publish ──
            logger.info("=== STEP 9: Publishing articles ===")
            publisher = ArticlePublisher(db)
            published = publisher.publish_batch(edited_articles, target_date, pipeline_run.id)
            summary["articles_published"] = len(published)

            # ── Done ──
            pipeline_run.status = PipelineStatus.COMPLETED
            pipeline_run.articles_generated = len(published)
            pipeline_run.completed_at = datetime.utcnow()
            db.commit()
            summary["status"] = "completed"

            logger.info(f"=== Pipeline completed: {len(published)} articles published ===")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            pipeline_run.status = PipelineStatus.FAILED
            pipeline_run.error_message = str(e)
            pipeline_run.completed_at = datetime.utcnow()
            db.commit()
            summary["status"] = "failed"
            summary["errors"].append(str(e))

        finally:
            db.close()

        return summary

    def _store_raw_posts(
        self, db: Session, todays_posts: list[dict], raw_data: dict,
        scrape_date: date, pipeline_run_id: int,
    ) -> list[RawPost]:
        """Store filtered posts in the database. Posts are already normalized by the scraper."""
        stored = []
        profiles_meta = raw_data.get("profiles_metadata", {})
        companies_meta = raw_data.get("companies_metadata", {})

        for post in todays_posts:
            author_name = post.get("authorName", "Unknown")
            target_url = post.get("targetUrl", "")

            # Try to match to a tracked profile or company
            profile = db.query(LinkedInProfile).filter(
                LinkedInProfile.linkedin_url.contains(target_url.rstrip("/").split("/")[-1])
            ).first() if "/in/" in target_url else None

            company = db.query(LinkedInCompany).filter(
                LinkedInCompany.linkedin_url.contains(target_url.rstrip("/").split("/")[-1])
            ).first() if "/company/" in target_url else None

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
                posted_at=post.get("_parsed_date"),
                scrape_date=scrape_date,
                likes_count=post.get("likesCount", 0),
                comments_count=post.get("commentsCount", 0),
                shares_count=post.get("sharesCount", 0),
                image_urls=post.get("images", []),
                raw_data=post.get("_raw"),
                pipeline_run_id=pipeline_run_id,
            )
            db.add(raw_post)
            stored.append(raw_post)

        db.commit()
        logger.info(f"Stored {len(stored)} raw posts")
        return stored

    def _posts_to_dicts(self, stored_posts: list[RawPost], original_posts: list[dict]) -> list[dict]:
        """Convert stored posts to dicts for labeling."""
        result = []
        for raw_post in stored_posts:
            result.append({
                "id": raw_post.id,
                "author_name": raw_post.author_name,
                "author_headline": raw_post.author_headline,
                "content_text": raw_post.content_text,
                "post_type": raw_post.post_type,
                "likes_count": raw_post.likes_count,
                "comments_count": raw_post.comments_count,
                "shares_count": raw_post.shares_count,
                "image_urls": raw_post.image_urls,
                "post_url": raw_post.post_url,
            })
        return result

    def _store_processed_posts(
        self, db: Session, labeled_posts: list[dict],
        embeddings: list, cluster_ids: list,
    ):
        """Store processed/labeled posts in the database."""
        for i, lp in enumerate(labeled_posts):
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
        logger.info(f"Stored {len(labeled_posts)} processed posts")

    def _detect_post_type(self, post: dict) -> str:
        """Detect the type of LinkedIn post."""
        if post.get("articleUrl"):
            return "article"
        if post.get("videoUrl"):
            return "video"
        if post.get("images") or post.get("imageUrl"):
            return "image"
        if post.get("document"):
            return "document"
        if post.get("poll"):
            return "poll"
        if post.get("reshared") or post.get("isRepost"):
            return "shared"
        return "original"
