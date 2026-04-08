"""API routes for articles — the main public-facing endpoints."""

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Article, ArticleImage
from backend.api.schemas import ArticleListItem, ArticleDetail, PaginatedResponse, CategoryCount
from backend.config import settings

router = APIRouter(prefix="/api/articles", tags=["articles"])

# ── Source profiles lookup (loaded once) ──
_source_profiles = None

def _get_source_profiles() -> list[dict]:
    global _source_profiles
    if _source_profiles is None:
        path = settings.data_dir / "source_profiles.json"
        if path.exists():
            with open(path) as f:
                _source_profiles = json.load(f)
        else:
            _source_profiles = []
    return _source_profiles


def _match_sources_for_article(article: Article) -> list[dict]:
    """Match source profiles to an article based on author_attribution text."""
    profiles = _get_source_profiles()
    if not profiles or not article.author_attribution:
        return []

    attr = article.author_attribution.lower()
    matched = []
    seen = set()
    for p in profiles:
        name = p.get("name", "")
        # Match if the source name appears in the attribution string
        if name.lower() in attr and name not in seen:
            matched.append(p)
            seen.add(name)
    return matched


@router.get("/", response_model=PaginatedResponse)
def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List published articles with pagination and filters."""
    query = db.query(Article).filter(Article.is_published == True)

    if category:
        query = query.filter(Article.category == category)
    if tag:
        query = query.filter(Article.tags.contains([tag]))
    if date_from:
        query = query.filter(Article.publish_date >= date_from)
    if date_to:
        query = query.filter(Article.publish_date <= date_to)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Article.headline.ilike(search_filter)) |
            (Article.summary.ilike(search_filter))
        )

    total = query.count()
    total_pages = math.ceil(total / page_size)

    articles = (
        query.order_by(Article.publish_date.desc(), Article.rank.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for a in articles:
        item = ArticleListItem.model_validate(a)
        item_dict = item.model_dump()
        item_dict["sources"] = _match_sources_for_article(a)
        items.append(item_dict)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/today")
def todays_articles(db: Session = Depends(get_db)):
    """Get all articles published today."""
    today = date.today()
    articles = (
        db.query(Article)
        .filter(Article.is_published == True, Article.publish_date == today)
        .order_by(Article.rank.asc())
        .all()
    )
    return [ArticleListItem.model_validate(a) for a in articles]


@router.get("/date/{publish_date}")
def articles_by_date(publish_date: date, db: Session = Depends(get_db)):
    """Get all articles for a specific date."""
    articles = (
        db.query(Article)
        .filter(Article.is_published == True, Article.publish_date == publish_date)
        .order_by(Article.rank.asc())
        .all()
    )
    return [ArticleListItem.model_validate(a) for a in articles]


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """Get all categories with article counts."""
    results = (
        db.query(Article.category, func.count(Article.id))
        .filter(Article.is_published == True)
        .group_by(Article.category)
        .order_by(func.count(Article.id).desc())
        .all()
    )
    return [CategoryCount(category=cat or "Uncategorized", count=cnt) for cat, cnt in results]


@router.get("/dates")
def available_dates(db: Session = Depends(get_db)):
    """Get all dates that have published articles."""
    results = (
        db.query(Article.publish_date, func.count(Article.id))
        .filter(Article.is_published == True)
        .group_by(Article.publish_date)
        .order_by(Article.publish_date.desc())
        .limit(90)
        .all()
    )
    return [{"date": d.isoformat(), "count": c} for d, c in results]


@router.get("/{slug}")
def get_article(slug: str, db: Session = Depends(get_db)):
    """Get a single article by slug, including matched source profiles."""
    article = db.query(Article).filter(Article.slug == slug, Article.is_published == True).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    detail = ArticleDetail.model_validate(article)
    result = detail.model_dump()
    result["sources"] = _match_sources_for_article(article)
    return result
