"""
AI-powered post labeling and categorization using Claude.
Extracts structured metadata from raw LinkedIn posts.
"""

import json
import logging
from typing import Optional

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)


LABELING_PROMPT = """You are a business news analyst specializing in the Kurdistan Region's business ecosystem.

Analyze the following LinkedIn post and extract structured metadata for a business news platform.

{author_context}

POST CONTENT:
Author: {author_name}
Headline: {author_headline}
Content: {content_text}
Post Type: {post_type}
Engagement: {likes} likes, {comments} comments, {shares} shares

Respond with a JSON object containing:
{{
    "summary": "A 2-3 sentence summary of the post's key message and business relevance",
    "category": "One of: Technology, Finance, Entrepreneurship, Marketing, HR & Talent, Investment, Real Estate, Education, Healthcare, Telecom, E-commerce, Infrastructure, Energy, Agriculture, Tourism, Government & Policy, Events, Partnerships, Product Launch, Company Update, Opinion & Thought Leadership",
    "tags": ["list", "of", "relevant", "tags", "max 5"],
    "sentiment": "positive, negative, neutral, or mixed",
    "key_entities": ["company names", "person names", "product names", "mentioned organizations"],
    "industry_sector": "Primary industry sector this relates to",
    "newsworthiness_score": 7.5,
    "news_angle": "Brief description of why this is newsworthy and what angle an article could take",
    "is_promotional": false,
    "business_impact": "Brief description of broader business impact or significance"
}}

The newsworthiness_score should be 1-10 based on:
- Relevance to Kurdistan Region business community (higher = more relevant)
- Uniqueness and novelty of the information
- Potential impact on the business ecosystem
- Engagement level relative to the content
- Whether it represents a genuine business development vs just self-promotion
- The author's authority and seniority (a CEO's insights carry more weight than a junior employee)
- If AUTHOR CONTEXT is provided above, use it to calibrate the score — senior leaders and major companies get a boost

Respond ONLY with the JSON object, no other text."""


class PostLabeler:
    """Labels and categorizes LinkedIn posts using Claude AI."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-haiku-4-5-20251001"  # Haiku for labeling (fast, cheap)
        self._memory_context_fn = None

    def set_memory_context_fn(self, fn):
        """Set a function that returns memory context for an author name."""
        self._memory_context_fn = fn

    def label_post(self, post_data: dict) -> Optional[dict]:
        """
        Analyze a single post and return structured labels.
        """
        content_text = post_data.get("content_text") or post_data.get("text") or ""

        if not content_text or len(content_text.strip()) < 20:
            logger.debug(f"Skipping post with insufficient content: {len(content_text)} chars")
            return None

        # Get memory context for this author if available
        author_context = ""
        if self._memory_context_fn:
            author_name = post_data.get("author_name", "")
            ctx = self._memory_context_fn(author_name)
            if ctx:
                author_context = ctx

        prompt = LABELING_PROMPT.format(
            author_name=post_data.get("author_name", "Unknown"),
            author_headline=post_data.get("author_headline", ""),
            content_text=content_text[:3000],
            post_type=post_data.get("post_type", "unknown"),
            likes=post_data.get("likes_count", 0),
            comments=post_data.get("comments_count", 0),
            shares=post_data.get("shares_count", 0),
            author_context=author_context,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text.strip()

            # Handle potential markdown code block wrapping
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

            labels = json.loads(result_text)
            logger.info(
                f"Labeled post by {post_data.get('author_name')}: "
                f"category={labels.get('category')}, score={labels.get('newsworthiness_score')}"
            )
            return labels

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse labeling response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error labeling post: {e}")
            return None

    def label_batch(self, posts: list[dict]) -> list[dict]:
        """
        Label a batch of posts. Returns list of (post, labels) tuples.
        Posts that fail labeling are returned with None labels.
        """
        results = []
        for i, post in enumerate(posts):
            logger.info(f"Labeling post {i + 1}/{len(posts)}...")
            labels = self.label_post(post)
            results.append({"post": post, "labels": labels})
        return results
