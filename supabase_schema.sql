-- Kurdistan Business Insight — Supabase Schema
-- Paste this in: https://supabase.com/dashboard → SQL Editor → New Query → Run
-- This drops old tables and creates the full schema.

DROP TABLE IF EXISTS incident_sources CASCADE;
DROP TABLE IF EXISTS incident_media CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;
DROP TABLE IF EXISTS tracked_accounts CASCADE;
DROP TABLE IF EXISTS article_images CASCADE;
DROP TABLE IF EXISTS article_sources CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TABLE IF EXISTS processed_posts CASCADE;
DROP TABLE IF EXISTS raw_posts CASCADE;
DROP TABLE IF EXISTS profile_memories CASCADE;
DROP TABLE IF EXISTS source_profiles CASCADE;
DROP TABLE IF EXISTS pipeline_runs CASCADE;
DROP TABLE IF EXISTS linkedin_companies CASCADE;
DROP TABLE IF EXISTS linkedin_profiles CASCADE;

CREATE TABLE linkedin_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    linkedin_url VARCHAR(500) NOT NULL UNIQUE,
    is_company BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE linkedin_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    linkedin_url VARCHAR(500) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'started',
    profiles_scraped INTEGER DEFAULT 0,
    posts_found INTEGER DEFAULT 0,
    posts_today INTEGER DEFAULT 0,
    articles_generated INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT,
    log JSONB DEFAULT '[]'
);

CREATE TABLE raw_posts (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES linkedin_profiles(id),
    company_id INTEGER REFERENCES linkedin_companies(id),
    linkedin_post_id VARCHAR(500) UNIQUE,
    post_url VARCHAR(1000),
    author_name VARCHAR(255) NOT NULL,
    author_headline VARCHAR(500),
    author_profile_url VARCHAR(500),
    content_text TEXT,
    post_type VARCHAR(50) DEFAULT 'original',
    posted_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT NOW(),
    scrape_date DATE NOT NULL,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    shares_count INTEGER DEFAULT 0,
    image_urls JSONB DEFAULT '[]',
    video_url VARCHAR(1000),
    article_url VARCHAR(1000),
    raw_data JSONB,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id)
);

CREATE TABLE processed_posts (
    id SERIAL PRIMARY KEY,
    raw_post_id INTEGER NOT NULL UNIQUE REFERENCES raw_posts(id),
    summary TEXT,
    category VARCHAR(100),
    tags JSONB DEFAULT '[]',
    sentiment VARCHAR(50),
    key_entities JSONB DEFAULT '[]',
    industry_sector VARCHAR(100),
    newsworthiness_score FLOAT DEFAULT 0.0,
    embedding JSONB,
    cluster_id INTEGER,
    processed_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(300) NOT NULL UNIQUE,
    headline VARCHAR(500) NOT NULL,
    subheadline VARCHAR(500),
    summary TEXT,
    body_html TEXT NOT NULL,
    body_markdown TEXT,
    category VARCHAR(100),
    tags JSONB DEFAULT '[]',
    featured_image_url VARCHAR(1000),
    featured_image_local VARCHAR(500),
    author_attribution TEXT,
    publish_date DATE NOT NULL,
    is_published BOOLEAN DEFAULT FALSE,
    reading_time_minutes INTEGER DEFAULT 3,
    rank INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id)
);

CREATE TABLE article_sources (
    article_id INTEGER REFERENCES articles(id),
    processed_post_id INTEGER REFERENCES processed_posts(id),
    PRIMARY KEY (article_id, processed_post_id)
);

CREATE TABLE article_images (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    image_url VARCHAR(1000),
    local_path VARCHAR(500),
    caption VARCHAR(500),
    is_featured BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE profile_memories (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER UNIQUE REFERENCES linkedin_profiles(id),
    company_id INTEGER UNIQUE REFERENCES linkedin_companies(id),
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) DEFAULT 'person',
    current_title VARCHAR(500),
    current_company VARCHAR(255),
    bio_summary TEXT,
    industry VARCHAR(255),
    location VARCHAR(255),
    follower_count INTEGER,
    experience JSONB DEFAULT '[]',
    education JSONB DEFAULT '[]',
    skills JSONB DEFAULT '[]',
    certifications JSONB DEFAULT '[]',
    achievements JSONB DEFAULT '[]',
    projects JSONB DEFAULT '[]',
    authority_score FLOAT DEFAULT 5.0,
    authority_reasoning TEXT,
    key_facts JSONB DEFAULT '[]',
    recent_topics JSONB DEFAULT '[]',
    business_relationships JSONB DEFAULT '[]',
    stance_and_opinions JSONB DEFAULT '[]',
    notable_quotes JSONB DEFAULT '[]',
    context_summary TEXT,
    last_profile_scrape TIMESTAMP,
    last_memory_update TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE source_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    linkedin_url VARCHAR(500),
    avatar_url TEXT,
    headline VARCHAR(500),
    type VARCHAR(50) DEFAULT 'profile'
);

-- Indexes
CREATE INDEX idx_articles_published ON articles(is_published, publish_date DESC);
CREATE INDEX idx_articles_slug ON articles(slug);
CREATE INDEX idx_articles_category ON articles(category);
CREATE INDEX idx_raw_posts_scrape_date ON raw_posts(scrape_date);

-- Row Level Security (public read)
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE linkedin_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE linkedin_companies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public_read_articles" ON articles FOR SELECT USING (is_published = true);
CREATE POLICY "public_read_images" ON article_images FOR SELECT USING (true);
CREATE POLICY "public_read_sources" ON source_profiles FOR SELECT USING (true);
CREATE POLICY "public_read_profiles" ON linkedin_profiles FOR SELECT USING (true);
CREATE POLICY "public_read_companies" ON linkedin_companies FOR SELECT USING (true);
