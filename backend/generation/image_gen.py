"""
Flux AI image generation for articles without photos.
Generates consistent branded illustrations using BFL's Flux API.
"""

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BFL_API_KEY = "bfl_pJlq13nkxWGXHZULc5IM4JRqCB5zkY8m"
BFL_BASE = "https://api.bfl.ai/v1"
MODEL = "flux-pro-1.1"  # Good balance of quality and cost

# Consistent brand style prefix for all generated images
STYLE_PREFIX = (
    "Minimalist modern editorial illustration, clean geometric shapes, "
    "muted color palette with black white and warm gold (#C8A960) accents, "
    "professional business magazine style, subtle gradients, "
    "no text or words in the image, abstract conceptual art. "
)


def generate_article_image(
    headline: str,
    category: str,
    summary: str = "",
    width: int = 1440,
    height: int = 768,
) -> Optional[str]:
    """
    Generate a branded illustration for an article.
    Returns the image URL or None on failure.
    """
    # Build a focused prompt from the article content
    prompt = (
        f"{STYLE_PREFIX}"
        f"Topic: {headline}. "
        f"Category: {category}. "
        f"{summary[:150] if summary else ''}"
    )

    logger.info(f"Generating image for: {headline[:50]}...")

    try:
        # Step 1: Submit generation request
        r = httpx.post(
            f"{BFL_BASE}/{MODEL}",
            headers={"x-key": BFL_API_KEY, "Content-Type": "application/json"},
            json={"prompt": prompt[:1000], "width": width, "height": height},
            timeout=30,
        )

        if r.status_code != 200:
            logger.error(f"Flux API error: {r.status_code} {r.text[:200]}")
            return None

        data = r.json()
        polling_url = data.get("polling_url")
        if not polling_url:
            request_id = data.get("id")
            polling_url = f"{BFL_BASE}/get_result?id={request_id}"

        # Step 2: Poll for result
        for _ in range(90):  # 90 seconds max
            time.sleep(1)
            result = httpx.get(polling_url, timeout=15)
            if result.status_code != 200:
                continue

            result_data = result.json()
            status = result_data.get("status")

            if status == "Ready":
                image_url = result_data.get("result", {}).get("sample")
                if image_url:
                    logger.info(f"Image generated: {image_url[:80]}")
                    return image_url

            elif status in ("Error", "Failed"):
                logger.error(f"Flux generation failed: {result_data}")
                return None

        logger.warning("Flux generation timed out")
        return None

    except Exception as e:
        logger.error(f"Flux API error: {e}")
        return None


def download_and_upload_image(image_url: str, slug: str) -> Optional[str]:
    """
    Download a Flux-generated image (expires in 10 min) and upload to Supabase Storage.
    Returns the permanent Supabase URL.
    """
    try:
        # Download from Flux (signed URL, expires quickly)
        r = httpx.get(image_url, timeout=30, follow_redirects=True)
        if r.status_code != 200:
            logger.error(f"Failed to download Flux image: {r.status_code}")
            return None

        image_bytes = r.content
        content_type = r.headers.get("content-type", "image/jpeg")

        # Upload to Supabase Storage
        from backend.database.supabase_client import SUPABASE_URL, SUPABASE_KEY
        ext = ".png" if "png" in content_type else ".jpg"
        filename = f"generated/{slug}{ext}"

        upload_r = httpx.post(
            f"{SUPABASE_URL}/storage/v1/object/article-images/{filename}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=image_bytes,
            timeout=30,
        )

        if upload_r.status_code in (200, 201):
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/article-images/{filename}"
            logger.info(f"Uploaded to Supabase Storage: {public_url}")
            return public_url
        else:
            logger.warning(f"Supabase Storage upload failed: {upload_r.status_code} {upload_r.text[:100]}")
            # Fall back to returning the Flux URL (expires in 10 min but works for now)
            return image_url

    except Exception as e:
        logger.error(f"Image download/upload error: {e}")
        return image_url  # Return Flux URL as fallback
