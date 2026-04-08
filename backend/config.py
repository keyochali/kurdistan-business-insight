import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    # Apify
    apify_api_token: str = os.getenv("APIFY_API_TOKEN", "")
    apify_user_id: str = os.getenv("APIFY_USER_ID", "")

    # Anthropic
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/newsletter.db")

    # App
    app_env: str = os.getenv("APP_ENV", "development")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Pipeline
    daily_article_count: int = int(os.getenv("DAILY_ARTICLE_COUNT", "20"))
    scrape_hour: int = int(os.getenv("SCRAPE_HOUR", "17"))
    scrape_minute: int = int(os.getenv("SCRAPE_MINUTE", "0"))
    timezone: str = os.getenv("TIMEZONE", "Asia/Baghdad")

    # Unsplash (optional)
    unsplash_access_key: str = os.getenv("UNSPLASH_ACCESS_KEY", "")

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    images_dir: Path = base_dir / "backend" / "static" / "images"

    class Config:
        env_file = ".env"


settings = Settings()
