"""Pydantic schemas for API request/response models."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class ArticleListItem(BaseModel):
    id: int
    slug: str
    headline: str
    subheadline: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = []
    featured_image_url: Optional[str] = None
    featured_image_local: Optional[str] = None
    author_attribution: Optional[str] = None
    publish_date: date
    reading_time_minutes: int = 3
    rank: Optional[int] = None

    class Config:
        from_attributes = True


class ArticleDetail(ArticleListItem):
    body_html: str
    body_markdown: Optional[str] = None
    is_published: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    images: list["ArticleImageSchema"] = []

    class Config:
        from_attributes = True


class ArticleImageSchema(BaseModel):
    id: int
    image_url: Optional[str] = None
    local_path: Optional[str] = None
    caption: Optional[str] = None
    is_featured: bool = False

    class Config:
        from_attributes = True


class PipelineRunSchema(BaseModel):
    id: int
    run_date: date
    status: str
    profiles_scraped: int = 0
    posts_found: int = 0
    posts_today: int = 0
    articles_generated: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class PipelineTriggerResponse(BaseModel):
    message: str
    pipeline_run_id: Optional[int] = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


class DateRange(BaseModel):
    start_date: date
    end_date: date


class CategoryCount(BaseModel):
    category: str
    count: int
