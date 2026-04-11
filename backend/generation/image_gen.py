"""
Flux AI image generation for articles without photos.
Generates branded illustrations with colors extracted from source logos.
"""

import io
import logging
import time
from typing import Optional

import httpx
from colorthief import ColorThief

logger = logging.getLogger(__name__)

BFL_API_KEY = "bfl_pJlq13nkxWGXHZULc5IM4JRqCB5zkY8m"
BFL_BASE = "https://api.bfl.ai/v1"
MODEL = "flux-pro-1.1"

STYLE_BASE = (
    "Professional business editorial photo-illustration. "
    "Show relevant real-world business objects and scenes: "
    "laptops, office buildings, handshakes, charts on screens, conference rooms, "
    "city skylines, factory floors, retail stores, construction sites, medical equipment, "
    "smartphones, logistics trucks, server rooms — whatever fits the article topic. "
    "Photorealistic 3D render style with shallow depth of field, soft studio lighting, "
    "clean composition, modern and premium feel. "
    "CRITICAL: absolutely no text, no letters, no words, no numbers, no captions, "
    "no writing of any kind anywhere in the image. "
)


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def extract_colors_from_url(image_url: str, count: int = 4) -> list[str]:
    """Download an image and extract dominant colors as hex strings."""
    try:
        r = httpx.get(image_url, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            return []
        ct = ColorThief(io.BytesIO(r.content))
        palette = ct.get_palette(color_count=count, quality=5)
        return [rgb_to_hex(c) for c in palette[:count]]
    except Exception as e:
        logger.debug(f"Color extraction failed for {image_url[:50]}: {e}")
        return []


def get_source_colors(sources: list[dict]) -> list[str]:
    """Extract colors from source profile avatars/logos."""
    all_colors = []
    for src in sources[:3]:  # max 3 sources
        avatar = src.get("avatar_url", "")
        if avatar:
            colors = extract_colors_from_url(avatar, count=3)
            all_colors.extend(colors)
    # Deduplicate and limit
    seen = set()
    unique = []
    for c in all_colors:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique[:5]


def build_color_prompt(colors: list[str]) -> str:
    """Build a strong color directive for the image prompt."""
    if not colors:
        return "The dominant colors must be black, white, and warm gold (#C8A960). "
    hex_list = ", ".join(colors[:4])
    return (
        f"IMPORTANT COLOR REQUIREMENT: The illustration MUST prominently feature "
        f"these exact brand colors as the dominant palette: {hex_list}. "
        f"These colors should be the most visible colors in the entire image. "
        f"Use them for backgrounds, shapes, gradients, and key visual elements. "
    )


def generate_article_image(
    headline: str,
    category: str,
    summary: str = "",
    sources: list[dict] = None,
    width: int = 1440,
    height: int = 768,
) -> Optional[str]:
    """
    Generate a branded illustration for an article.
    Extracts colors from source logos for brand-aligned images.
    Returns the image URL or None on failure.
    """
    # Extract colors from source avatars/logos
    colors = get_source_colors(sources or [])
    color_directive = build_color_prompt(colors)
    if colors:
        logger.info(f"  Brand colors from sources: {colors}")

    prompt = (
        f"{STYLE_BASE}"
        f"{color_directive}"
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
