"""
Post-process articles to inject inline images into body_html.
Places up to 3 images between paragraphs, evenly distributed through the article.
"""
import sqlite3
import re

MAX_INLINE = 3
API_STATIC = "/static/"


def build_image_html(src, idx):
    """Build a styled inline figure element."""
    return (
        f'<figure class="article-inline-image" data-img-idx="{idx}">'
        f'<img src="{src}" alt="" loading="lazy" />'
        f'</figure>'
    )


def inject_images_into_html(body_html, image_paths):
    """
    Insert images between paragraphs in the HTML.
    Distributes them evenly: after roughly 1/4, 1/2, 3/4 of the content.
    """
    if not image_paths or not body_html:
        return body_html

    images_to_insert = image_paths[:MAX_INLINE]

    # Split on closing paragraph/heading tags to find insertion points
    # We look for </p>, </h2>, </h3>, </blockquote>, </ul> as natural break points
    parts = re.split(r'(</(?:p|h[23]|blockquote|ul)>)', body_html)

    # Count actual content blocks (pairs of content + closing tag)
    block_count = len([p for p in parts if re.match(r'</(?:p|h[23]|blockquote|ul)>', p)])

    if block_count < 3:
        # Too short, just put one image at the end
        return body_html + build_image_html(images_to_insert[0], 0)

    # Calculate insertion points: distribute evenly
    n = len(images_to_insert)
    # Place after these block indices (1-indexed)
    # For 3 images in 12 blocks: after blocks 3, 6, 9
    # For 2 images in 8 blocks: after blocks 3, 5
    # For 1 image in 6 blocks: after block 3
    spacing = block_count // (n + 1)
    insert_after_blocks = [spacing * (i + 1) for i in range(n)]

    # Rebuild HTML with images injected
    result = []
    block_idx = 0
    img_idx = 0

    for part in parts:
        result.append(part)

        # Check if this is a closing tag (a block boundary)
        if re.match(r'</(?:p|h[23]|blockquote|ul)>', part):
            block_idx += 1
            if img_idx < len(images_to_insert) and block_idx in insert_after_blocks:
                result.append(build_image_html(images_to_insert[img_idx], img_idx))
                img_idx += 1

    return "".join(result)


def main():
    conn = sqlite3.connect("data/newsletter.db")
    c = conn.cursor()

    # Get all articles with their extra images
    c.execute("""
        SELECT a.id, a.headline, a.body_html, a.featured_image_url
        FROM articles a
        WHERE a.is_published = 1
    """)
    articles = c.fetchall()

    updated = 0
    for art_id, headline, body_html, feat_url in articles:
        # Skip if already has inline images
        if "article-inline-image" in (body_html or ""):
            continue

        # Get extra images for this article (not featured)
        c.execute("""
            SELECT local_path, image_url FROM article_images
            WHERE article_id = ? AND is_featured = 0
            LIMIT ?
        """, (art_id, MAX_INLINE))
        extra_imgs = c.fetchall()

        if not extra_imgs:
            continue

        # Build URLs for inline images
        inline_urls = []
        for local_path, image_url in extra_imgs:
            if local_path:
                inline_urls.append(f"{API_STATIC}{local_path}")
            elif image_url:
                inline_urls.append(image_url)

        if not inline_urls:
            continue

        new_html = inject_images_into_html(body_html, inline_urls)

        if new_html != body_html:
            c.execute("UPDATE articles SET body_html = ? WHERE id = ?", (new_html, art_id))
            updated += 1
            n = len(inline_urls)
            print(f"  #{art_id}: injected {n} image(s) into: {headline[:60]}")

    conn.commit()
    conn.close()
    print(f"\nDone. Updated {updated} articles with inline images.")


if __name__ == "__main__":
    main()
