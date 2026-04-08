# Kurdistan Business Insight

AI-powered daily business news platform that generates 20 curated articles every day from the LinkedIn activity of Kurdistan Region's most active business leaders and companies.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DAILY PIPELINE (5:00 PM)                      │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  SCRAPE   │→│ PROCESS  │→│  SELECT  │→│ WRITE → EDIT → PUB│ │
│  │  Apify    │  │ Label    │  │ Top 20   │  │ Claude AI        │ │
│  │  LinkedIn │  │ Embed    │  │ Stories  │  │ Quality Pipeline │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   FastAPI Backend  │
                    │   SQLite Database  │
                    │   REST API         │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   React Frontend  │
                    │   Tailwind CSS    │
                    │   Premium Design  │
                    └───────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Apify account & API key
- Anthropic (Claude) API key

### 1. Clone and setup environment

```bash
cd LinkedinNewsLetter

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys
```

### 2. Backend setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r backend/requirements.txt

# Start backend server
python -m uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend setup

```bash
cd frontend
npm install
npm start
```

### 4. Trigger the pipeline (manually)

```bash
# Via API
curl -X POST http://localhost:8000/api/admin/pipeline/run

# Or let the scheduler run at the configured time (default: 5:00 PM Baghdad time)
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `APIFY_API_TOKEN` | Apify API token for LinkedIn scraping | Yes |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | Yes |
| `DATABASE_URL` | SQLite or PostgreSQL connection string | No (default: SQLite) |
| `DAILY_ARTICLE_COUNT` | Number of articles to generate daily | No (default: 20) |
| `SCRAPE_HOUR` | Hour to run pipeline (24h format) | No (default: 17) |
| `TIMEZONE` | Timezone for scheduling | No (default: Asia/Baghdad) |

## Project Structure

```
LinkedinNewsLetter/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration management
│   ├── pipeline.py          # Daily pipeline orchestrator
│   ├── scheduler.py         # APScheduler for daily runs
│   ├── database/
│   │   ├── models.py        # SQLAlchemy data models
│   │   └── connection.py    # Database connection
│   ├── scraper/
│   │   ├── apify_client.py  # Apify LinkedIn scraper
│   │   └── post_filter.py   # Date filtering & image extraction
│   ├── processing/
│   │   ├── labeler.py       # AI post labeling (Claude)
│   │   └── embeddings.py    # Embedding generation & clustering
│   ├── generation/
│   │   ├── selector.py      # AI topic selection (top 20)
│   │   ├── writer.py        # AI article writer
│   │   ├── editor.py        # AI article editor/reviewer
│   │   └── publisher.py     # Database publisher & image downloader
│   └── api/
│       ├── schemas.py       # Pydantic request/response models
│       └── routes/
│           ├── articles.py  # Public article endpoints
│           └── admin.py     # Admin & pipeline endpoints
├── frontend/
│   └── src/
│       ├── components/      # React components
│       ├── pages/           # Page components
│       └── utils/           # API client
├── data/
│   ├── profiles.json        # 29 tracked LinkedIn profiles
│   └── companies.json       # 17 tracked companies
├── docker-compose.yml
└── .env.example
```

## API Endpoints

### Public
- `GET /api/articles/` — List articles (paginated, filterable)
- `GET /api/articles/today` — Today's articles
- `GET /api/articles/date/{date}` — Articles by date
- `GET /api/articles/{slug}` — Single article detail
- `GET /api/articles/categories` — Category list with counts
- `GET /api/articles/dates` — Available dates

### Admin
- `POST /api/admin/pipeline/run` — Trigger pipeline manually
- `GET /api/admin/pipeline/runs` — List pipeline runs
- `GET /api/admin/stats` — Platform statistics

## Pipeline Details

The daily pipeline runs in 9 steps:

1. **Scrape** — Apify collects posts from 46 LinkedIn accounts
2. **Filter** — Only posts from today are kept
3. **Store** — Raw posts saved to database
4. **Label** — Claude AI categorizes each post (topic, sentiment, entities, newsworthiness 1-10)
5. **Embed** — sentence-transformers generates embeddings, posts clustered by similarity
6. **Select** — Claude AI picks top 20 stories ensuring diversity
7. **Write** — Claude AI writes detailed 400-700 word articles for each
8. **Edit** — Claude AI reviews for accuracy, quality, and style
9. **Publish** — Articles saved with downloaded images

## Data Sources

### Tracked Profiles (29)
Business leaders from Kurdistan Region including entrepreneurs, executives, and industry leaders.

### Tracked Companies (17)
Major companies including Lezzoo, Asiacell, BlackAce Tech, Avesta Group, First Iraqi Bank, and more.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, APScheduler
- **AI**: Claude (Anthropic) for labeling, selection, writing, editing
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Scraping**: Apify (harvestapi/linkedin-profile-posts)
- **Frontend**: React 18, Tailwind CSS, React Router
- **Database**: SQLite (development) / PostgreSQL (production)
