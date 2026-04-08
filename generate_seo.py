"""Generate SEO files: sitemap.xml, robots.txt, and pre-rendered meta HTML for each article."""
import json
import os
from datetime import datetime

SITE_URL = "https://frontend-eight-azure-29.vercel.app"
PUBLIC_DIR = "frontend/public"


def generate_sitemap():
    with open(f"{PUBLIC_DIR}/data.json") as f:
        data = json.load(f)

    urls = [
        {"loc": SITE_URL, "priority": "1.0", "changefreq": "daily"},
        {"loc": f"{SITE_URL}/archive", "priority": "0.6", "changefreq": "daily"},
    ]

    for article in data["articles"]:
        if article.get("is_published"):
            urls.append({
                "loc": f"{SITE_URL}/article/{article['slug']}",
                "lastmod": article.get("publish_date", ""),
                "priority": "0.8",
                "changefreq": "monthly",
            })

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        xml += "  <url>\n"
        xml += f"    <loc>{u['loc']}</loc>\n"
        if u.get("lastmod"):
            xml += f"    <lastmod>{u['lastmod']}</lastmod>\n"
        xml += f"    <changefreq>{u['changefreq']}</changefreq>\n"
        xml += f"    <priority>{u['priority']}</priority>\n"
        xml += "  </url>\n"
    xml += "</urlset>\n"

    with open(f"{PUBLIC_DIR}/sitemap.xml", "w") as f:
        f.write(xml)
    print(f"Generated sitemap.xml with {len(urls)} URLs")


def generate_robots():
    robots = f"""User-agent: *
Allow: /
Disallow: /admin

Sitemap: {SITE_URL}/sitemap.xml
"""
    with open(f"{PUBLIC_DIR}/robots.txt", "w") as f:
        f.write(robots)
    print("Generated robots.txt")


def generate_prerender_meta():
    """
    Generate a meta.json with per-article SEO data.
    This is used by a prerender script or can be consumed by the app.
    """
    with open(f"{PUBLIC_DIR}/data.json") as f:
        data = json.load(f)

    meta = {}
    for article in data["articles"]:
        if not article.get("is_published"):
            continue
        slug = article["slug"]
        meta[slug] = {
            "title": f"{article['headline']} — Kurdistan Business Insight",
            "description": (article.get("summary") or article.get("subheadline") or "")[:160],
            "image": article.get("featured_image_url") or "",
            "url": f"{SITE_URL}/article/{slug}",
            "published": article.get("publish_date", ""),
            "category": article.get("category", ""),
            "author": article.get("author_attribution", ""),
        }

    with open(f"{PUBLIC_DIR}/meta.json", "w") as f:
        json.dump(meta, f)
    print(f"Generated meta.json for {len(meta)} articles")


if __name__ == "__main__":
    generate_sitemap()
    generate_robots()
    generate_prerender_meta()
