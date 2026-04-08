"""
Weekly LinkedIn profile detail scraper.
Fetches bio, experience, education, skills, certifications for tracked profiles.
Uses Apify's linkedin-profile-scraper actor.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from apify_client import ApifyClient
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.models import ProfileMemory, LinkedInProfile, LinkedInCompany

logger = logging.getLogger(__name__)

# Apify actor for detailed profile scraping
PROFILE_ACTOR = "apify/linkedin-profile-scraper"
COMPANY_ACTOR = "apify/linkedin-company-scraper"


class ProfileDetailScraper:
    """Scrapes full LinkedIn profile/company details for weekly memory updates."""

    def __init__(self):
        self.client = ApifyClient(settings.apify_api_token)

    def scrape_profile_details(self, urls: list[str]) -> list[dict]:
        """Scrape detailed profile data from LinkedIn profile URLs."""
        if not urls:
            return []

        logger.info(f"Scraping {len(urls)} profile details...")

        run_input = {
            "startUrls": [{"url": u} for u in urls],
            "proxy": {"useApifyProxy": True},
        }

        try:
            run = self.client.actor(PROFILE_ACTOR).call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            logger.info(f"Scraped {len(items)} profile details")
            return items
        except Exception as e:
            logger.error(f"Error scraping profiles: {e}")
            return []

    def scrape_company_details(self, urls: list[str]) -> list[dict]:
        """Scrape detailed company data from LinkedIn company URLs."""
        if not urls:
            return []

        logger.info(f"Scraping {len(urls)} company details...")

        run_input = {
            "startUrls": [{"url": u} for u in urls],
            "proxy": {"useApifyProxy": True},
        }

        try:
            run = self.client.actor(COMPANY_ACTOR).call(run_input=run_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            logger.info(f"Scraped {len(items)} company details")
            return items
        except Exception as e:
            logger.error(f"Error scraping companies: {e}")
            return []

    def update_memories_from_profiles(self, db: Session, profile_data: list[dict]):
        """Update ProfileMemory records with scraped profile details."""
        for data in profile_data:
            name = data.get("fullName") or data.get("name", "")
            if not name:
                continue

            memory = db.query(ProfileMemory).filter(
                ProfileMemory.entity_name.ilike(f"%{name.split()[0]}%"),
                ProfileMemory.entity_type == "person",
            ).first()

            if not memory:
                continue

            # Update static fields
            memory.current_title = data.get("headline") or data.get("title")
            memory.location = data.get("location") or data.get("addressLocality")
            memory.bio_summary = data.get("summary") or data.get("about")
            memory.follower_count = data.get("followersCount") or data.get("connections")

            # Experience
            experience = []
            for exp in (data.get("experience") or data.get("positions") or []):
                experience.append({
                    "title": exp.get("title", ""),
                    "company": exp.get("companyName") or exp.get("company", ""),
                    "duration": exp.get("duration") or exp.get("dateRange", ""),
                    "description": (exp.get("description") or "")[:300],
                })
            if experience:
                memory.experience = experience

            # Education
            education = []
            for edu in (data.get("education") or data.get("schools") or []):
                education.append({
                    "school": edu.get("schoolName") or edu.get("name", ""),
                    "degree": edu.get("degreeName") or edu.get("degree", ""),
                    "field": edu.get("fieldOfStudy") or edu.get("field", ""),
                })
            if education:
                memory.education = education

            # Skills
            skills = data.get("skills") or []
            if skills:
                memory.skills = [s if isinstance(s, str) else s.get("name", "") for s in skills][:15]

            # Certifications
            certs = data.get("certifications") or []
            if certs:
                memory.certifications = [
                    {"name": c.get("name", ""), "issuer": c.get("authority", "")}
                    for c in certs
                ]

            memory.last_profile_scrape = datetime.utcnow()
            logger.info(f"Updated profile memory for {name}")

        db.commit()

    def update_memories_from_companies(self, db: Session, company_data: list[dict]):
        """Update ProfileMemory records with scraped company details."""
        for data in company_data:
            name = data.get("name", "")
            if not name:
                continue

            memory = db.query(ProfileMemory).filter(
                ProfileMemory.entity_name.ilike(f"%{name.split()[0]}%"),
                ProfileMemory.entity_type == "company",
            ).first()

            if not memory:
                continue

            memory.bio_summary = data.get("description") or data.get("about")
            memory.industry = data.get("industry") or data.get("industries", [""])[0] if data.get("industries") else None
            memory.location = data.get("headquarter") or data.get("locations", [""])[0] if data.get("locations") else None
            memory.follower_count = data.get("followersCount") or data.get("followers")
            memory.current_title = data.get("tagline")

            if data.get("specialities") or data.get("specialties"):
                memory.skills = (data.get("specialities") or data.get("specialties", []))[:15]

            memory.last_profile_scrape = datetime.utcnow()
            logger.info(f"Updated company memory for {name}")

        db.commit()

    def run_weekly_update(self, db: Session):
        """Run the full weekly profile detail scrape and update."""
        logger.info("=== Starting weekly profile detail scrape ===")

        # Get profile URLs
        profiles = db.query(LinkedInProfile).filter_by(is_active=True).all()
        profile_urls = [p.linkedin_url for p in profiles]

        # Get company URLs
        companies = db.query(LinkedInCompany).filter_by(is_active=True).all()
        company_urls = [c.linkedin_url for c in companies]

        # Scrape and update
        if profile_urls:
            profile_data = self.scrape_profile_details(profile_urls)
            if profile_data:
                self.update_memories_from_profiles(db, profile_data)

        if company_urls:
            company_data = self.scrape_company_details(company_urls)
            if company_data:
                self.update_memories_from_companies(db, company_data)

        logger.info("=== Weekly profile scrape complete ===")
