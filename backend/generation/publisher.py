"""
Publishes edited articles to the database and downloads associated images.
"""

import hashlib
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import httpx
from slugify import slugify
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.models import Article, ArticleImage, ProcessedPost

logger = logging.getLogger(__name__)


class ArticlePublisher:
    """Saves finalized articles to the database."""

    def __init__(self, db: Session):
        self.db = db
        self.images_dir = settings.images_dir
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def publish_article(
        self,
        article_data: dict,
        publish_date: date,
        pipeline_run_id: Optional[int] = None,
    ) -> Article:
        """
        Save a finalized article to the database.
        Downloads featured image if available.
        """
        headline = article_data.get("headline", "Untitled")
        slug = self._generate_slug(headline, publish_date)

        # Check for duplicate
        existing = self.db.query(Article).filter_by(slug=slug).first()
        if existing:
            logger.info(f"Article already exists: {slug}")
            return existing

        # Download featured image
        featured_image_local = None
        source_posts = article_data.get("source_selection", {}).get("source_posts", [])
        image_url = self._find_best_image(source_posts)

        if image_url:
            featured_image_local = self._download_image(image_url, slug)

        # Upload to Supabase Storage so we don't hotlink LinkedIn CDN (which blocks it)
        stored_image_url = image_url
        if featured_image_local and image_url and "licdn.com" in image_url:
            supabase_url = self._upload_to_supabase_storage(featured_image_local, slug)
            if supabase_url:
                stored_image_url = supabase_url

        article = Article(
            slug=slug,
            headline=headline,
            subheadline=article_data.get("subheadline", ""),
            summary=article_data.get("summary", ""),
            body_html=article_data.get("body_html", ""),
            body_markdown=article_data.get("body_markdown", ""),
            category=article_data.get("category", "General"),
            tags=article_data.get("tags", []),
            featured_image_url=stored_image_url,
            featured_image_local=featured_image_local,
            author_attribution=article_data.get("author_attribution", ""),
            publish_date=publish_date,
            is_published=True,
            reading_time_minutes=article_data.get("reading_time_minutes", 3),
            rank=article_data.get("rank", 0),
            pipeline_run_id=pipeline_run_id,
        )

        self.db.add(article)
        self.db.flush()

        # Save additional images
        for img_url in self._collect_all_images(source_posts):
            if img_url == image_url:
                continue  # Skip featured image
            img_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
            local = self._download_image(img_url, f"{slug}-{img_hash}")
            # Upload to Supabase Storage if it's a LinkedIn URL
            stored_url = img_url
            if local and "licdn.com" in img_url:
                supabase_url = self._upload_to_supabase_storage(local, f"{slug}-{img_hash}")
                if supabase_url:
                    stored_url = supabase_url
            img = ArticleImage(
                article_id=article.id,
                image_url=stored_url,
                local_path=local,
                is_featured=False,
            )
            self.db.add(img)

        # Inject up to 3 inline images into body_html
        extra_locals = [
            img.local_path for img in self.db.query(ArticleImage)
            .filter_by(article_id=article.id, is_featured=False)
            .limit(3).all()
            if img.local_path
        ]
        if extra_locals:
            base = settings.frontend_url.replace(":3000", ":8000") if ":3000" in settings.frontend_url else f"http://localhost:{settings.app_port}"
            article.body_html = self._inject_inline_images(
                article.body_html, [f"{base}/static/{p}" for p in extra_locals]
            )

        self.db.commit()
        logger.info(f"Published article: {headline} ({slug})")
        return article

    def publish_batch(
        self,
        articles: list[dict],
        publish_date: date,
        pipeline_run_id: Optional[int] = None,
    ) -> list[Article]:
        """Publish all articles."""
        published = []
        for i, article_data in enumerate(articles):
            logger.info(f"Publishing article {i + 1}/{len(articles)}...")
            try:
                article = self.publish_article(article_data, publish_date, pipeline_run_id)
                published.append(article)
            except Exception as e:
                logger.error(f"Error publishing article: {e}")
                self.db.rollback()

        logger.info(f"Published {len(published)}/{len(articles)} articles")
        return published

    def _generate_slug(self, headline: str, pub_date: date) -> str:
        base = slugify(headline, max_length=200)
        return f"{pub_date.isoformat()}-{base}"

    def _find_best_image(self, source_posts: list[dict]) -> Optional[str]:
        """Find the best image from source posts."""
        for sp in source_posts:
            post = sp.get("post", {})
            images = post.get("image_urls") or post.get("images") or []
            if isinstance(images, list) and images:
                return images[0]
            image = post.get("imageUrl") or post.get("image")
            if image:
                return image
        return None

    def _collect_all_images(self, source_posts: list[dict]) -> list[str]:
        """Collect all images from source posts."""
        all_images = []
        for sp in source_posts:
            post = sp.get("post", {})
            images = post.get("image_urls") or post.get("images") or []
            if isinstance(images, list):
                all_images.extend(images)
        return list(set(all_images))

    def _download_image(self, url: str, filename: str) -> Optional[str]:
        """Download an image and save locally."""
        try:
            response = httpx.get(url, timeout=15, follow_redirects=True)
            if response.status_code != 200:
                return None

            content_type = response.headers.get("content-type", "")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"
            elif "gif" in content_type:
                ext = ".gif"

            filepath = self.images_dir / f"{filename}{ext}"
            filepath.write_bytes(response.content)
            # Return path relative to the static mount (forward slashes for URLs)
            rel = filepath.relative_to(settings.base_dir / "backend" / "static")
            return str(rel).replace("\\", "/")

        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
            return None

    def _upload_to_supabase_storage(self, local_path: str, slug: str) -> Optional[str]:
        """Upload a locally downloaded image to Supabase Storage and return the public URL.
        LinkedIn CDN URLs block hotlinking, so we must serve images from our own storage."""
        try:
            from backend.database.supabase_client import SUPABASE_URL, SUPABASE_KEY

            filepath = self.images_dir.parent / local_path
            if not filepath.exists():
                return None

            image_bytes = filepath.read_bytes()
            ext = filepath.suffix.lower()
            content_type = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
            storage_path = f"linkedin/{slug}{ext}"

            r = httpx.post(
                f"{SUPABASE_URL}/storage/v1/object/article-images/{storage_path}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=image_bytes,
                timeout=30,
            )

            if r.status_code in (200, 201):
                public_url = f"{SUPABASE_URL}/storage/v1/object/public/article-images/{storage_path}"
                logger.info(f"Uploaded to Supabase Storage: {public_url}")
                return public_url

            logger.warning(f"Supabase Storage upload failed: {r.status_code}")
            return None
        except Exception as e:
            logger.warning(f"Supabase Storage upload error: {e}")
            return None

    @staticmethod
    def _inject_inline_images(body_html: str, image_urls: list[str]) -> str:
        """Insert up to 3 images between paragraphs, evenly distributed."""
        if not image_urls or not body_html:
            return body_html

        imgs = image_urls[:3]
        parts = re.split(r'(</(?:p|h[23]|blockquote|ul)>)', body_html)
        block_count = len([p for p in parts if re.match(r'</(?:p|h[23]|blockquote|ul)>', p)])

        if block_count < 3:
            return body_html

        spacing = block_count // (len(imgs) + 1)
        insert_after = {spacing * (i + 1) for i in range(len(imgs))}

        result, block_idx, img_idx = [], 0, 0
        for part in parts:
            result.append(part)
            if re.match(r'</(?:p|h[23]|blockquote|ul)>', part):
                block_idx += 1
                if img_idx < len(imgs) and block_idx in insert_after:
                    result.append(
                        f'<figure class="article-inline-image">'
                        f'<img src="{imgs[img_idx]}" alt="" loading="lazy" />'
                        f'</figure>'
                    )
                    img_idx += 1

        return "".join(result)
