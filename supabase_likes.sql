-- Add likes system to Kurdistan Business Insight
-- Paste this in: Supabase Dashboard → SQL Editor → New Query → Run

-- Add likes_count to articles
ALTER TABLE articles ADD COLUMN IF NOT EXISTS likes_count INTEGER DEFAULT 0;

-- Create likes tracking table (prevents duplicate likes)
CREATE TABLE IF NOT EXISTS article_likes (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    fingerprint VARCHAR(64) NOT NULL,  -- hash of IP + user-agent
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_likes_article ON article_likes(article_id);
CREATE INDEX IF NOT EXISTS idx_likes_fingerprint ON article_likes(fingerprint);

-- RLS: anyone can read likes count (via articles), service role can insert
ALTER TABLE article_likes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public_read_likes" ON article_likes FOR SELECT USING (true);
CREATE POLICY "service_insert_likes" ON article_likes FOR INSERT WITH CHECK (true);

-- Update the articles read policy to include likes_count
DROP POLICY IF EXISTS "public_read_articles" ON articles;
CREATE POLICY "public_read_articles" ON articles FOR SELECT USING (is_published = true);
