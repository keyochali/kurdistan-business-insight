"""Set up Supabase database via REST API: reset, create schema, migrate data from SQLite."""
import json
import sqlite3
import httpx

SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzMTg2MywiZXhwIjoyMDg4NDA3ODYzfQ.NxlhFmuFlAwhXZlTDclGXEGUOepFOnHyCXjM6bEV0mc"
SQLITE_PATH = "data/newsletter.db"

headers = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def run_sql(sql):
    """Execute SQL via Supabase's pg_net/rpc or direct REST."""
    r = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/",
        headers={**headers, "Content-Profile": "public"},
        json={"query": sql},
        timeout=30,
    )
    # If rpc doesn't work, try the management API
    if r.status_code >= 400:
        # Use the SQL query endpoint via management API
        pass
    return r


def insert_rows(table, rows):
    """Insert rows via Supabase REST API."""
    if not rows:
        return
    # Batch insert
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        r = httpx.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={**headers, "Prefer": "return=minimal,resolution=ignore-duplicates"},
            json=batch,
            timeout=30,
        )
        if r.status_code >= 400:
            print(f"  Error inserting into {table}: {r.status_code} {r.text[:200]}")
        else:
            print(f"  Inserted {len(batch)} rows into {table}")


def migrate_data():
    """Migrate data from SQLite to Supabase via REST API."""
    lite = sqlite3.connect(SQLITE_PATH)
    lite.row_factory = sqlite3.Row

    # 1. Profiles
    rows = lite.execute("SELECT name, linkedin_url, is_company, is_active FROM linkedin_profiles").fetchall()
    insert_rows("linkedin_profiles", [
        {"name": r["name"], "linkedin_url": r["linkedin_url"], "is_company": bool(r["is_company"]), "is_active": bool(r["is_active"])}
        for r in rows
    ])
    print(f"Migrated {len(rows)} profiles")

    # 2. Companies
    rows = lite.execute("SELECT name, linkedin_url, is_active FROM linkedin_companies").fetchall()
    insert_rows("linkedin_companies", [
        {"name": r["name"], "linkedin_url": r["linkedin_url"], "is_active": bool(r["is_active"])}
        for r in rows
    ])
    print(f"Migrated {len(rows)} companies")

    # 3. Source profiles
    try:
        with open("data/source_profiles.json") as f:
            sources = json.load(f)
        insert_rows("source_profiles", [
            {"name": s["name"], "linkedin_url": s["linkedin_url"], "avatar_url": s["avatar_url"],
             "headline": s.get("headline", ""), "type": s.get("type", "profile")}
            for s in sources
        ])
        print(f"Migrated {len(sources)} source profiles")
    except FileNotFoundError:
        print("No source_profiles.json")

    # 4. Articles
    rows = lite.execute("SELECT * FROM articles WHERE is_published = 1").fetchall()
    articles = []
    for r in rows:
        tags = r["tags"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except:
                tags = []
        articles.append({
            "slug": r["slug"],
            "headline": r["headline"],
            "subheadline": r["subheadline"],
            "summary": r["summary"],
            "body_html": r["body_html"],
            "body_markdown": r["body_markdown"],
            "category": r["category"],
            "tags": tags,
            "featured_image_url": r["featured_image_url"],
            "featured_image_local": r["featured_image_local"],
            "author_attribution": r["author_attribution"],
            "publish_date": r["publish_date"],
            "is_published": True,
            "reading_time_minutes": r["reading_time_minutes"],
            "rank": r["rank"],
        })
    insert_rows("articles", articles)
    print(f"Migrated {len(articles)} articles")

    # 5. Article images — need article IDs first
    # Get the new article IDs from Supabase
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/articles?select=id,slug&is_published=eq.true",
        headers=headers,
        timeout=30,
    )
    if r.status_code == 200:
        slug_to_id = {a["slug"]: a["id"] for a in r.json()}

        img_rows = lite.execute("""
            SELECT ai.*, a.slug FROM article_images ai
            JOIN articles a ON ai.article_id = a.id
        """).fetchall()
        images = []
        for row in img_rows:
            new_id = slug_to_id.get(row["slug"])
            if new_id:
                images.append({
                    "article_id": new_id,
                    "image_url": row["image_url"],
                    "local_path": row["local_path"],
                    "caption": row["caption"],
                    "is_featured": bool(row["is_featured"]),
                })
        insert_rows("article_images", images)
        print(f"Migrated {len(images)} article images")

    lite.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    print("=== Migrating data to Supabase ===")
    # Tables already created via Supabase dashboard SQL editor
    # We just need to insert data via REST API
    migrate_data()
