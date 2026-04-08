"""Admin API routes for pipeline management, CMS, and monitoring."""

import json
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import (
    PipelineRun, Article, RawPost, LinkedInProfile, LinkedInCompany,
)
from backend.api.schemas import PipelineRunSchema, PipelineTriggerResponse
from backend.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ── Pipeline status tracking ──
_pipeline_status = {
    "running": False,
    "step": None,
    "started_at": None,
}


# ── Pipeline triggers ──

@router.post("/pipeline/scrape")
def trigger_scrape(db: Session = Depends(get_db)):
    """Scrape new posts and generate articles. Runs full pipeline in background."""
    if _pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    def run():
        _pipeline_status["running"] = True
        _pipeline_status["step"] = "starting"
        try:
            # Run the pipeline script as a subprocess so it picks up all changes
            result = subprocess.run(
                [sys.executable, "run_pipeline.py"],
                cwd=str(settings.base_dir),
                capture_output=True, text=True, timeout=1800,
            )
            _pipeline_status["step"] = "completed" if result.returncode == 0 else "failed"
        except Exception as e:
            _pipeline_status["step"] = f"error: {str(e)[:100]}"
        finally:
            _pipeline_status["running"] = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return {"message": "Scrape & generate pipeline started", "status": "running"}


@router.post("/pipeline/regenerate")
def trigger_regenerate(db: Session = Depends(get_db)):
    """Re-generate articles from cached posts (no scraping). Clears old articles first."""
    if _pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    def run():
        _pipeline_status["running"] = True
        _pipeline_status["step"] = "clearing old articles"
        try:
            # Clear today's articles
            from backend.database.models import ArticleImage, ArticleSource
            db_inner = next(get_db())
            db_inner.query(ArticleImage).delete()
            db_inner.execute(ArticleSource.__table__.delete())
            db_inner.query(Article).delete()
            from backend.database.models import ProcessedPost
            db_inner.query(ProcessedPost).delete()
            db_inner.query(PipelineRun).delete()
            db_inner.commit()
            db_inner.close()

            _pipeline_status["step"] = "regenerating"
            result = subprocess.run(
                [sys.executable, "run_pipeline.py"],
                cwd=str(settings.base_dir),
                capture_output=True, text=True, timeout=1800,
            )
            _pipeline_status["step"] = "completed" if result.returncode == 0 else "failed"
        except Exception as e:
            _pipeline_status["step"] = f"error: {str(e)[:100]}"
        finally:
            _pipeline_status["running"] = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return {"message": "Regeneration started (using cached posts)", "status": "running"}


@router.get("/pipeline/status")
def get_pipeline_status():
    """Get current pipeline status."""
    return _pipeline_status


@router.get("/pipeline/runs")
def list_pipeline_runs(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List recent pipeline runs."""
    runs = (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [PipelineRunSchema.model_validate(r) for r in runs]


# ── Profile CRUD ──

class EntityCreate(BaseModel):
    name: str
    linkedin_url: str


@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db)):
    """List all tracked profiles."""
    profiles = db.query(LinkedInProfile).order_by(LinkedInProfile.name).all()
    return [{"id": p.id, "name": p.name, "linkedin_url": p.linkedin_url, "is_active": p.is_active} for p in profiles]


@router.post("/profiles")
def add_profile(data: EntityCreate, db: Session = Depends(get_db)):
    """Add a new tracked profile."""
    existing = db.query(LinkedInProfile).filter_by(linkedin_url=data.linkedin_url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")
    profile = LinkedInProfile(name=data.name, linkedin_url=data.linkedin_url)
    db.add(profile)
    db.commit()

    # Also update profiles.json
    _sync_profiles_json(db)
    return {"id": profile.id, "name": profile.name, "linkedin_url": profile.linkedin_url, "is_active": True}


@router.delete("/profiles/{profile_id}")
def remove_profile(profile_id: int, db: Session = Depends(get_db)):
    """Remove a tracked profile."""
    profile = db.query(LinkedInProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.is_active = False
    db.commit()
    _sync_profiles_json(db)
    return {"message": f"Profile '{profile.name}' deactivated"}


# ── Company CRUD ──

@router.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    """List all tracked companies."""
    companies = db.query(LinkedInCompany).order_by(LinkedInCompany.name).all()
    return [{"id": c.id, "name": c.name, "linkedin_url": c.linkedin_url, "is_active": c.is_active} for c in companies]


@router.post("/companies")
def add_company(data: EntityCreate, db: Session = Depends(get_db)):
    """Add a new tracked company."""
    existing = db.query(LinkedInCompany).filter_by(linkedin_url=data.linkedin_url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company already exists")
    company = LinkedInCompany(name=data.name, linkedin_url=data.linkedin_url)
    db.add(company)
    db.commit()
    _sync_companies_json(db)
    return {"id": company.id, "name": company.name, "linkedin_url": company.linkedin_url, "is_active": True}


@router.delete("/companies/{company_id}")
def remove_company(company_id: int, db: Session = Depends(get_db)):
    """Remove a tracked company."""
    company = db.query(LinkedInCompany).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.is_active = False
    db.commit()
    _sync_companies_json(db)
    return {"message": f"Company '{company.name}' deactivated"}


# ── Stats & Sources ──

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get overall platform statistics."""
    total_articles = db.query(Article).filter(Article.is_published == True).count()
    total_posts = db.query(RawPost).count()
    total_runs = db.query(PipelineRun).count()
    latest_run = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()
    return {
        "total_articles": total_articles,
        "total_posts_scraped": total_posts,
        "total_pipeline_runs": total_runs,
        "latest_run": PipelineRunSchema.model_validate(latest_run) if latest_run else None,
    }


@router.get("/sources")
def list_sources():
    """Get all tracked source profiles with avatars."""
    path = settings.data_dir / "source_profiles.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


@router.delete("/articles/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db)):
    """Unpublish an article (soft delete)."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.is_published = False
    db.commit()
    return {"message": f"Article '{article.headline}' unpublished"}


# ── Helpers ──

def _sync_profiles_json(db: Session):
    """Write active profiles to profiles.json for the scraper."""
    profiles = db.query(LinkedInProfile).filter_by(is_active=True).all()
    data = [{"name": p.name, "url": p.linkedin_url} for p in profiles]
    path = settings.data_dir / "profiles.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _sync_companies_json(db: Session):
    """Write active companies to companies.json for the scraper."""
    companies = db.query(LinkedInCompany).filter_by(is_active=True).all()
    data = [{"name": c.name, "url": c.linkedin_url} for c in companies]
    path = settings.data_dir / "companies.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
