"""
FastAPI application — main entry point for the backend.
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database.connection import init_db, SessionLocal
from backend.database.models import LinkedInProfile, LinkedInCompany
from backend.scheduler import start_scheduler, stop_scheduler
from backend.api.routes.articles import router as articles_router
from backend.api.routes.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def seed_profiles_and_companies():
    """Load profiles and companies from JSON into the database if not already present."""
    db = SessionLocal()
    try:
        profiles_path = settings.data_dir / "profiles.json"
        if profiles_path.exists():
            with open(profiles_path) as f:
                profiles = json.load(f)
            for p in profiles:
                existing = db.query(LinkedInProfile).filter_by(linkedin_url=p["url"]).first()
                if not existing:
                    db.add(LinkedInProfile(name=p["name"], linkedin_url=p["url"]))
            db.commit()
            logger.info(f"Seeded {len(profiles)} profiles")

        companies_path = settings.data_dir / "companies.json"
        if companies_path.exists():
            with open(companies_path) as f:
                companies = json.load(f)
            for c in companies:
                existing = db.query(LinkedInCompany).filter_by(linkedin_url=c["url"]).first()
                if not existing:
                    db.add(LinkedInCompany(name=c["name"], linkedin_url=c["url"]))
            db.commit()
            logger.info(f"Seeded {len(companies)} companies")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    logger.info("Initializing database...")
    init_db()
    seed_profiles_and_companies()

    logger.info("Starting scheduler...")
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Kurdistan Business Insight",
    description="AI-powered daily business news from Kurdistan Region's LinkedIn community",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:5173",
        "https://frontend-eight-azure-29.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (images)
images_dir = settings.images_dir
images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(settings.base_dir / "backend" / "static")), name="static")

# Routes
app.include_router(articles_router)
app.include_router(admin_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Kurdistan Business Insight API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.app_port, reload=True)
