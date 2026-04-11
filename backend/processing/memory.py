"""
Profile memory system — extracts and maintains contextual knowledge
about tracked LinkedIn profiles and companies.

Two update cycles:
  - Daily: Extract insights from new posts (key facts, opinions, topics)
  - Weekly: Scrape full profile data (bio, experience, skills, education)

Memory is used internally to enrich AI prompts — never displayed publicly.
"""

import json
import logging
from datetime import datetime, date
from typing import Optional

import anthropic
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.models import (
    ProfileMemory, LinkedInProfile, LinkedInCompany, RawPost,
)

logger = logging.getLogger(__name__)


# ── Daily: Extract insights from posts ──

POST_MEMORY_PROMPT = """You are building a knowledge profile about a person or company from their LinkedIn activity.

ENTITY: {entity_name} ({entity_type})
CURRENT KNOWN CONTEXT:
{existing_context}

NEW POST(S) from today:
{posts_text}

Analyze these posts and extract ONLY memory-worthy information — facts that would help a journalist write better, more contextual articles about this person/company in the future.

Extract:
1. **key_facts**: Concrete facts (new partnerships, product launches, hires, milestones, funding, expansions, awards). NOT opinions or motivational content.
2. **topics**: Business topics they're actively engaged with
3. **relationships**: Companies, people, or organizations they mention or work with
4. **stances**: Clear business opinions or positions they've taken on industry topics
5. **quotes**: Notable direct quotes worth remembering
6. **authority_update**: Based on everything you know, rate their authority/influence in Kurdistan's business scene (1-10) with brief reasoning
7. **context_update**: If the new posts add meaningful context, provide an updated 2-3 sentence summary of who this entity is and why they matter in Kurdistan's business ecosystem

Respond with JSON:
{{
    "new_facts": ["{{"date": "2026-04-07", "fact": "...", "importance": "high/medium/low"}}"],
    "topics": ["topic1", "topic2"],
    "relationships": ["{{"entity": "Company X", "relationship": "partner"}}"],
    "stances": ["{{"topic": "...", "stance": "...", "date": "2026-04-07"}}"],
    "quotes": ["{{"quote": "...", "context": "..."}}"],
    "authority_score": 7.5,
    "authority_reasoning": "...",
    "context_summary": "Updated summary or null if no meaningful update",
    "has_meaningful_update": true
}}

Set has_meaningful_update to false if the posts are just motivational content, reshares, or don't add real knowledge. Only return new_facts for genuinely newsworthy information.

Respond ONLY with JSON."""


PROFILE_ANALYSIS_PROMPT = """You are analyzing a LinkedIn profile to build a comprehensive knowledge profile for a business intelligence platform focused on Kurdistan Region.

PROFILE DATA:
Name: {name}
Headline: {headline}
Type: {entity_type}
LinkedIn URL: {url}
Followers: {followers}

Posts (recent activity):
{posts_summary}

Based on all available information, create a comprehensive profile analysis:

{{
    "bio_summary": "2-3 sentence professional summary of who they are and what they do",
    "industry": "Primary industry sector",
    "current_title": "Their current job title or company tagline",
    "current_company": "Company they work at (or company name if entity is a company)",
    "skills": ["key skill/expertise areas, max 8"],
    "achievements": ["notable achievements or milestones mentioned"],
    "authority_score": 7.0,
    "authority_reasoning": "Why this score — consider: seniority, company size, followers, post quality, industry influence",
    "context_summary": "2-3 paragraph rich context summary. Who is this entity? What's their role in Kurdistan's business ecosystem? What makes their content valuable? What themes do they focus on?"
}}

authority_score guide:
- 9-10: C-suite at major company, government leader, investor with major deals
- 7-8: Senior executive, founder of notable startup, industry thought leader
- 5-6: Mid-level professional, small business owner, active community member
- 3-4: Junior professional, small following, limited business impact
- 1-2: Student, inactive, purely personal content

Respond ONLY with JSON."""


class MemoryManager:
    """Manages the profile memory system."""

    def __init__(self, db: Session):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-haiku-4-5-20251001"  # Haiku for memory extraction (fast, cheap)

    def ensure_all_memories_exist(self):
        """Create ProfileMemory records for any profiles/companies that don't have one."""
        profiles = self.db.query(LinkedInProfile).filter_by(is_active=True).all()
        for p in profiles:
            existing = self.db.query(ProfileMemory).filter_by(profile_id=p.id).first()
            if not existing:
                mem = ProfileMemory(
                    profile_id=p.id,
                    entity_name=p.name,
                    entity_type="person",
                )
                self.db.add(mem)
                logger.info(f"Created memory for profile: {p.name}")

        companies = self.db.query(LinkedInCompany).filter_by(is_active=True).all()
        for c in companies:
            existing = self.db.query(ProfileMemory).filter_by(company_id=c.id).first()
            if not existing:
                mem = ProfileMemory(
                    company_id=c.id,
                    entity_name=c.name,
                    entity_type="company",
                )
                self.db.add(mem)
                logger.info(f"Created memory for company: {c.name}")

        self.db.commit()

    def update_daily_memories(self, scrape_date: date) -> int:
        """
        Extract insights from today's posts and update memories.
        Returns number of memories updated.
        """
        updated = 0

        # Get all raw posts from today grouped by author
        posts = (
            self.db.query(RawPost)
            .filter(RawPost.scrape_date == scrape_date)
            .all()
        )

        # Group posts by author identity (profile_id or company_id)
        author_posts = {}
        for post in posts:
            if post.profile_id:
                key = ("profile", post.profile_id)
            elif post.company_id:
                key = ("company", post.company_id)
            else:
                continue
            author_posts.setdefault(key, []).append(post)

        for (entity_type_key, entity_id), post_list in author_posts.items():
            if entity_type_key == "profile":
                memory = self.db.query(ProfileMemory).filter_by(profile_id=entity_id).first()
            else:
                memory = self.db.query(ProfileMemory).filter_by(company_id=entity_id).first()

            if not memory:
                continue

            # Skip if posts have no real content
            content_posts = [p for p in post_list if p.content_text and len(p.content_text.strip()) > 30]
            if not content_posts:
                continue

            success = self._extract_post_insights(memory, content_posts)
            if success:
                updated += 1

        self.db.commit()
        logger.info(f"Updated {updated} profile memories from daily posts")
        return updated

    def _extract_post_insights(self, memory: ProfileMemory, posts: list[RawPost]) -> bool:
        """Use Claude to extract memory-worthy insights from posts."""
        posts_text = ""
        for p in posts:
            posts_text += (
                f"--- Post ({p.likes_count} likes, {p.comments_count} comments) ---\n"
                f"{p.content_text}\n\n"
            )

        existing_context = memory.context_summary or "No prior context available."
        if memory.key_facts:
            recent_facts = memory.key_facts[-5:] if isinstance(memory.key_facts, list) else []
            if recent_facts:
                existing_context += "\nRecent known facts:\n"
                for f in recent_facts:
                    existing_context += f"- {f.get('fact', '')}\n"

        prompt = POST_MEMORY_PROMPT.format(
            entity_name=memory.entity_name,
            entity_type=memory.entity_type,
            existing_context=existing_context,
            posts_text=posts_text[:4000],
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response.content[0].text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

            data = json.loads(result_text)

            if not data.get("has_meaningful_update", False):
                logger.debug(f"No meaningful update for {memory.entity_name}")
                return False

            # Merge new facts (append, keep last 50)
            existing_facts = memory.key_facts or []
            new_facts = [f for f in data.get("new_facts", []) if f.get("importance") != "low"]
            memory.key_facts = (existing_facts + new_facts)[-50:]

            # Update topics (merge, keep unique, last 15)
            existing_topics = set(memory.recent_topics or [])
            new_topics = set(data.get("topics", []))
            memory.recent_topics = list(existing_topics | new_topics)[-15:]

            # Merge relationships
            existing_rels = memory.business_relationships or []
            new_rels = data.get("relationships", [])
            seen_entities = {r.get("entity", "").lower() for r in existing_rels}
            for r in new_rels:
                if r.get("entity", "").lower() not in seen_entities:
                    existing_rels.append(r)
            memory.business_relationships = existing_rels[-30:]

            # Merge stances
            existing_stances = memory.stance_and_opinions or []
            memory.stance_and_opinions = (existing_stances + data.get("stances", []))[-20:]

            # Merge quotes
            existing_quotes = memory.notable_quotes or []
            memory.notable_quotes = (existing_quotes + data.get("quotes", []))[-10:]

            # Update authority
            if data.get("authority_score"):
                memory.authority_score = data["authority_score"]
                memory.authority_reasoning = data.get("authority_reasoning", "")

            # Update context summary if provided
            if data.get("context_summary"):
                memory.context_summary = data["context_summary"]

            memory.last_memory_update = datetime.utcnow()
            logger.info(f"Updated memory for {memory.entity_name}: {len(new_facts)} new facts")
            return True

        except Exception as e:
            logger.error(f"Error extracting insights for {memory.entity_name}: {e}")
            return False

    def seed_from_scraped_data(self, raw_scrape_path: str = "data/raw_scrape.json"):
        """Seed initial memories from existing scraped post data."""
        self.ensure_all_memories_exist()

        try:
            with open(raw_scrape_path) as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning("No raw_scrape.json found for seeding")
            return

        all_posts = data.get("company_posts", []) + data.get("profile_posts", [])

        # Group by author
        author_data = {}
        for post in all_posts:
            raw = post.get("_raw", {})
            author = raw.get("author", {})
            name = author.get("name", "")
            if not name:
                continue

            if name not in author_data:
                avatar = author.get("avatar", {})
                author_data[name] = {
                    "name": name,
                    "headline": author.get("info", ""),
                    "url": author.get("linkedinUrl", ""),
                    "type": author.get("type", "profile"),
                    "followers": None,
                    "posts": [],
                }
                # Try to parse follower count from headline
                headline = author.get("info", "")
                if "followers" in headline:
                    try:
                        count_str = headline.split("followers")[0].strip().replace(",", "")
                        author_data[name]["followers"] = int(count_str)
                    except (ValueError, IndexError):
                        pass

            text = post.get("text", "")
            if text and len(text.strip()) > 30:
                author_data[name]["posts"].append({
                    "text": text[:500],
                    "likes": post.get("likesCount", 0),
                    "comments": post.get("commentsCount", 0),
                })

        # Now update each memory with initial profile analysis
        for name, adata in author_data.items():
            memory = self.db.query(ProfileMemory).filter_by(entity_name=name).first()
            if not memory:
                # Try fuzzy match
                memory = self.db.query(ProfileMemory).filter(
                    ProfileMemory.entity_name.ilike(f"%{name.split()[0]}%")
                ).first()

            if not memory:
                continue

            if memory.context_summary and memory.authority_score != 5.0:
                logger.debug(f"Memory already seeded for {name}, skipping")
                continue

            # Update follower count
            if adata.get("followers"):
                memory.follower_count = adata["followers"]

            posts_summary = ""
            for p in adata["posts"][:10]:
                posts_summary += f"- ({p['likes']} likes) {p['text'][:200]}\n"

            if not posts_summary:
                posts_summary = "No recent posts available."

            # Use Claude for initial analysis
            prompt = PROFILE_ANALYSIS_PROMPT.format(
                name=name,
                headline=adata["headline"],
                entity_type=adata["type"],
                url=adata["url"],
                followers=adata.get("followers", "Unknown"),
                posts_summary=posts_summary,
            )

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                result_text = response.content[0].text.strip()
                if result_text.startswith("```"):
                    result_text = result_text.split("\n", 1)[1]
                    if result_text.endswith("```"):
                        result_text = result_text[:-3]
                    result_text = result_text.strip()

                profile = json.loads(result_text)

                memory.bio_summary = profile.get("bio_summary")
                memory.industry = profile.get("industry")
                memory.current_title = profile.get("current_title")
                memory.current_company = profile.get("current_company")
                memory.skills = profile.get("skills", [])
                memory.achievements = profile.get("achievements", [])
                memory.authority_score = profile.get("authority_score", 5.0)
                memory.authority_reasoning = profile.get("authority_reasoning", "")
                memory.context_summary = profile.get("context_summary", "")
                memory.last_profile_scrape = datetime.utcnow()

                logger.info(f"Seeded memory for {name} (authority: {memory.authority_score})")

            except Exception as e:
                logger.error(f"Error seeding memory for {name}: {e}")

        self.db.commit()
        logger.info("Memory seeding complete")

    def get_context_for_post(self, author_name: str) -> str:
        """Get memory context string for use in AI prompts."""
        memory = self.db.query(ProfileMemory).filter(
            ProfileMemory.entity_name.ilike(f"%{author_name.split()[0]}%")
        ).first()

        if not memory or not memory.context_summary:
            return ""

        parts = [f"[AUTHOR CONTEXT: {memory.entity_name}]"]
        parts.append(f"Authority: {memory.authority_score}/10 — {memory.authority_reasoning or ''}")

        if memory.current_title:
            parts.append(f"Role: {memory.current_title}")
        if memory.current_company:
            parts.append(f"Company: {memory.current_company}")
        if memory.bio_summary:
            parts.append(f"Bio: {memory.bio_summary}")
        if memory.context_summary:
            parts.append(f"Context: {memory.context_summary}")
        if memory.key_facts:
            recent = memory.key_facts[-3:]
            facts = "; ".join(f.get("fact", "") for f in recent if f.get("fact"))
            if facts:
                parts.append(f"Recent facts: {facts}")
        if memory.recent_topics:
            parts.append(f"Active topics: {', '.join(memory.recent_topics[:5])}")

        return "\n".join(parts)

    def get_all_authority_scores(self) -> dict[str, float]:
        """Return a {name: score} dict for all entities."""
        memories = self.db.query(ProfileMemory).all()
        return {m.entity_name: m.authority_score or 5.0 for m in memories}
