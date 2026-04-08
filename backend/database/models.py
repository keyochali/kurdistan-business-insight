import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, JSON, Date, Enum as SAEnum,
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class PostType(str, enum.Enum):
    ORIGINAL = "original"
    SHARED = "shared"
    ARTICLE = "article"
    DOCUMENT = "document"
    VIDEO = "video"
    IMAGE = "image"
    POLL = "poll"
    OTHER = "other"


class PipelineStatus(str, enum.Enum):
    STARTED = "started"
    SCRAPING = "scraping"
    PROCESSING = "processing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class LinkedInProfile(Base):
    __tablename__ = "linkedin_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    linkedin_url = Column(String(500), nullable=False, unique=True)
    is_company = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    posts = relationship("RawPost", back_populates="profile")


class LinkedInCompany(Base):
    __tablename__ = "linkedin_companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    linkedin_url = Column(String(500), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    posts = relationship("RawPost", back_populates="company")


class RawPost(Base):
    __tablename__ = "raw_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("linkedin_profiles.id"), nullable=True)
    company_id = Column(Integer, ForeignKey("linkedin_companies.id"), nullable=True)
    linkedin_post_id = Column(String(500), unique=True, nullable=True)
    post_url = Column(String(1000), nullable=True)
    author_name = Column(String(255), nullable=False)
    author_headline = Column(String(500), nullable=True)
    author_profile_url = Column(String(500), nullable=True)
    content_text = Column(Text, nullable=True)
    post_type = Column(String(50), default=PostType.ORIGINAL)
    posted_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=datetime.datetime.utcnow)
    scrape_date = Column(Date, nullable=False)
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    image_urls = Column(JSON, default=list)
    video_url = Column(String(1000), nullable=True)
    article_url = Column(String(1000), nullable=True)
    raw_data = Column(JSON, nullable=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id"), nullable=True)

    profile = relationship("LinkedInProfile", back_populates="posts")
    company = relationship("LinkedInCompany", back_populates="posts")
    processed_post = relationship("ProcessedPost", back_populates="raw_post", uselist=False)
    pipeline_run = relationship("PipelineRun", back_populates="raw_posts")


class ProcessedPost(Base):
    __tablename__ = "processed_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_post_id = Column(Integer, ForeignKey("raw_posts.id"), nullable=False, unique=True)
    summary = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=list)
    sentiment = Column(String(50), nullable=True)
    key_entities = Column(JSON, default=list)
    industry_sector = Column(String(100), nullable=True)
    newsworthiness_score = Column(Float, default=0.0)
    embedding = Column(JSON, nullable=True)
    cluster_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)

    raw_post = relationship("RawPost", back_populates="processed_post")
    articles = relationship("Article", secondary="article_sources", back_populates="source_posts")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(300), unique=True, nullable=False)
    headline = Column(String(500), nullable=False)
    subheadline = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    body_html = Column(Text, nullable=False)
    body_markdown = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=list)
    featured_image_url = Column(String(1000), nullable=True)
    featured_image_local = Column(String(500), nullable=True)
    author_attribution = Column(Text, nullable=True)
    publish_date = Column(Date, nullable=False)
    is_published = Column(Boolean, default=False)
    reading_time_minutes = Column(Integer, default=3)
    rank = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id"), nullable=True)

    images = relationship("ArticleImage", back_populates="article", cascade="all, delete-orphan")
    source_posts = relationship("ProcessedPost", secondary="article_sources", back_populates="articles")
    pipeline_run = relationship("PipelineRun", back_populates="articles")


class ArticleSource(Base):
    """Association table linking articles to their source processed posts."""
    __tablename__ = "article_sources"

    article_id = Column(Integer, ForeignKey("articles.id"), primary_key=True)
    processed_post_id = Column(Integer, ForeignKey("processed_posts.id"), primary_key=True)


class ArticleImage(Base):
    __tablename__ = "article_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    image_url = Column(String(1000), nullable=True)
    local_path = Column(String(500), nullable=True)
    caption = Column(String(500), nullable=True)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    article = relationship("Article", back_populates="images")


class ProfileMemory(Base):
    """
    Long-term memory for each tracked LinkedIn profile or company.
    Stores both static profile data (updated weekly) and dynamic
    post-derived insights (updated daily). Used internally to enrich
    AI prompts — never exposed on the website.
    """
    __tablename__ = "profile_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Link to tracked profile or company (one of these will be set)
    profile_id = Column(Integer, ForeignKey("linkedin_profiles.id"), nullable=True, unique=True)
    company_id = Column(Integer, ForeignKey("linkedin_companies.id"), nullable=True, unique=True)
    entity_name = Column(String(255), nullable=False)
    entity_type = Column(String(50), default="person")  # "person" or "company"

    # ── Static profile data (weekly scrape) ──
    current_title = Column(String(500), nullable=True)
    current_company = Column(String(255), nullable=True)
    bio_summary = Column(Text, nullable=True)         # AI-condensed bio
    industry = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    follower_count = Column(Integer, nullable=True)

    # Structured data stored as JSON
    experience = Column(JSON, default=list)            # [{title, company, duration, description}]
    education = Column(JSON, default=list)             # [{school, degree, field, year}]
    skills = Column(JSON, default=list)                # ["skill1", "skill2"]
    certifications = Column(JSON, default=list)        # [{name, issuer, year}]
    achievements = Column(JSON, default=list)          # ["achievement1", ...]
    projects = Column(JSON, default=list)              # [{name, description, role}]

    # Computed influence/authority score (0-10)
    authority_score = Column(Float, default=5.0)
    authority_reasoning = Column(Text, nullable=True)  # Why this score

    # ── Dynamic memory (daily post extraction) ──
    key_facts = Column(JSON, default=list)             # [{date, fact, source}]
    recent_topics = Column(JSON, default=list)         # ["topic1", "topic2"]
    business_relationships = Column(JSON, default=list)  # [{entity, relationship}]
    stance_and_opinions = Column(JSON, default=list)   # [{topic, stance, date}]
    notable_quotes = Column(JSON, default=list)        # [{quote, date, context}]

    # AI-generated context summary (refreshed daily)
    context_summary = Column(Text, nullable=True)      # 2-3 paragraph summary for AI prompts

    # Timestamps
    last_profile_scrape = Column(DateTime, nullable=True)
    last_memory_update = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    profile = relationship("LinkedInProfile", foreign_keys=[profile_id])
    company = relationship("LinkedInCompany", foreign_keys=[company_id])


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(Date, nullable=False)
    status = Column(String(50), default=PipelineStatus.STARTED)
    profiles_scraped = Column(Integer, default=0)
    posts_found = Column(Integer, default=0)
    posts_today = Column(Integer, default=0)
    articles_generated = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    log = Column(JSON, default=list)

    raw_posts = relationship("RawPost", back_populates="pipeline_run")
    articles = relationship("Article", back_populates="pipeline_run")
