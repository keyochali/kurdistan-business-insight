"""Admin API routes for pipeline management and monitoring."""

import json
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import PipelineRun, Article, RawPost
from backend.api.schemas import PipelineRunSchema, PipelineTriggerResponse
from backend.pipeline import DailyPipeline
from backend.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/pipeline/run", response_model=PipelineTriggerResponse)
def trigger_pipeline(
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Manually trigger the daily pipeline. Runs in background thread."""
    pipeline = DailyPipeline()

    def run_pipeline():
        pipeline.run(target_date)

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    return PipelineTriggerResponse(
        message=f"Pipeline triggered for {target_date or 'today'}. Running in background.",
    )


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


@router.get("/pipeline/runs/{run_id}", response_model=PipelineRunSchema)
def get_pipeline_run(run_id: int, db: Session = Depends(get_db)):
    """Get details of a specific pipeline run."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return PipelineRunSchema.model_validate(run)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get overall platform statistics."""
    total_articles = db.query(Article).filter(Article.is_published == True).count()
    total_posts = db.query(RawPost).count()
    total_runs = db.query(PipelineRun).count()
    latest_run = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()

    dates_with_articles = (
        db.query(Article.publish_date)
        .filter(Article.is_published == True)
        .distinct()
        .count()
    )

    return {
        "total_articles": total_articles,
        "total_posts_scraped": total_posts,
        "total_pipeline_runs": total_runs,
        "days_with_articles": dates_with_articles,
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
