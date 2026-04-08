# Architecture & Implementation Guide

## System Architecture

### High-Level Flow

```
LinkedIn Profiles (29) ──┐
                          ├──→ Apify Scraper ──→ Date Filter ──→ Raw Posts DB
LinkedIn Companies (17) ──┘                                          │
                                                                     ▼
                                                              AI Labeler (Claude)
                                                                     │
                                                                     ▼
                                                            Embeddings + Clustering
                                                                     │
                                                                     ▼
                                                        AI Article Selector (Claude)
                                                         (picks top 20 stories)
                                                                     │
                                                                     ▼
                                                        AI Article Writer (Claude)
                                                         (writes each article)
                                                                     │
                                                                     ▼
                                                        AI Article Editor (Claude)
                                                         (reviews & polishes)
                                                                     │
                                                                     ▼
                                                            Publisher (DB + Images)
                                                                     │
                                                                     ▼
                                                         FastAPI REST API ──→ React Frontend
```

## Component Details

### 1. Scraper Layer (`backend/scraper/`)

**Apify Client** (`apify_client.py`):
- Uses `harvestapi/linkedin-profile-posts` actor
- Scrapes profiles in batches of 10 to avoid rate limits
- Handles both personal profiles and company pages
- Returns raw post data from Apify's dataset

**Post Filter** (`post_filter.py`):
- Parses multiple date formats (ISO, Unix timestamps, relative dates like "2h", "1d")
- Filters to only include posts published today (Kurdistan timezone)
- Extracts image URLs from various post structures
- Handles Apify's inconsistent date field naming

### 2. Processing Layer (`backend/processing/`)

**Labeler** (`labeler.py`):
- Uses Claude to analyze each post individually
- Extracts: summary, category, tags, sentiment, key entities, industry sector
- Rates newsworthiness (1-10) based on relevance, novelty, impact
- Detects promotional content vs genuine business news

**Categories**: Technology, Finance, Entrepreneurship, Marketing, HR & Talent, Investment, Real Estate, Education, Healthcare, Telecom, E-commerce, Infrastructure, Energy, Events, Partnerships, Product Launch, Company Update, Opinion & Thought Leadership

**Embedding Engine** (`embeddings.py`):
- Uses sentence-transformers `all-MiniLM-L6-v2` model (runs locally)
- Builds composite text from content + summary + tags for richer embeddings
- Agglomerative clustering groups related posts
- Cosine similarity for finding related articles

### 3. Generation Layer (`backend/generation/`)

**Selector** (`selector.py`):
- Sends all processed posts (max 60) to Claude as editorial director
- Selection criteria prioritizes: genuine business news > diversity > impact > unique insight
- Avoids: motivational quotes, pure self-promotion, reshares
- Returns ranked list of 20 selections with headline angles

**Writer** (`writer.py`):
- Claude writes 400-700 word articles in business journalism style
- Structure: lead paragraph → context → analysis → supporting details → forward-looking close
- Attributes original LinkedIn authors naturally
- Outputs: headline, subheadline, summary, body (markdown), tags

**Editor** (`editor.py`):
- Claude reviews each article for: accuracy, headline quality, structure, clarity, tone
- Cross-references against source material for fact-checking
- Assigns quality score (1-10)
- Converts markdown to semantic HTML

**Publisher** (`publisher.py`):
- Generates URL slugs with date prefix
- Downloads featured images from LinkedIn posts
- Stores articles in database with full metadata
- Handles duplicate detection

### 4. Data Layer (`backend/database/`)

**Key Models**:
- `LinkedInProfile` / `LinkedInCompany` — tracked accounts
- `RawPost` — scraped LinkedIn data with engagement metrics
- `ProcessedPost` — labeled data with embeddings and clusters
- `Article` — final published articles with HTML content
- `PipelineRun` — execution logs for monitoring

### 5. API Layer (`backend/api/`)

**Public Endpoints** (`routes/articles.py`):
- Paginated article listing with category/tag/date/search filters
- Single article by slug
- Category and date indexes

**Admin Endpoints** (`routes/admin.py`):
- Manual pipeline trigger
- Pipeline run monitoring
- Platform statistics
- Article unpublish (soft delete)

### 6. Frontend (`frontend/src/`)

**Design**: Premium news website inspired by Bloomberg/TechCrunch
- Dark navy header with gold accent branding
- Featured hero article with side-by-side layout
- Card grid for remaining articles
- Category filter badges with color coding
- Article detail page with semantic typography
- Responsive design (mobile-first)
- Loading skeletons for perceived performance

## Pipeline Timing & Costs

### Estimated Daily Run
- **Apify**: ~5 actor runs (batches of 10) ≈ $1-3/day depending on post volume
- **Claude API**: ~50-80 calls/day (labeling + selection + writing + editing) ≈ $2-5/day
- **Total**: ~$3-8/day estimated

### Performance
- Scraping: 5-15 minutes (depends on Apify queue)
- Labeling: 3-5 minutes (sequential Claude calls)
- Selection: 30 seconds (single Claude call)
- Writing: 5-10 minutes (20 articles sequentially)
- Editing: 5-10 minutes (20 articles sequentially)
- **Total pipeline**: 20-40 minutes

## Deployment Options

### Option A: VPS (Recommended for start)
1. Deploy on a VPS (DigitalOcean, Hetzner, Linode)
2. Run backend with systemd or PM2
3. Serve frontend with Nginx
4. SQLite for database (sufficient for this scale)

### Option B: Docker
1. Use provided `docker-compose.yml`
2. Single `docker-compose up -d` to run everything

### Option C: Cloud
1. Backend on Railway/Render/Fly.io
2. Frontend on Vercel/Netlify
3. PostgreSQL on Supabase/Neon

## Adding New Profiles/Companies

1. Edit `data/profiles.json` or `data/companies.json`
2. Restart the backend (profiles are seeded on startup)
3. New profiles will be included in the next pipeline run

## Monitoring

- Check `/api/admin/stats` for overall platform health
- Check `/api/admin/pipeline/runs` for daily pipeline status
- Each pipeline run logs detailed step-by-step progress
- Failed runs store error messages for debugging
