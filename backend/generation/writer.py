"""
AI article writer that generates detailed, well-structured business news articles
from selected LinkedIn posts and their metadata.
"""

import json
import logging
import re

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)


WRITER_PROMPT = """You are a senior business journalist writing for "Kurdistan Business Insight" — a premium daily business news platform covering the Kurdistan Region.

Write a detailed, well-structured business news article based on the following LinkedIn post(s) and editorial direction.

EDITORIAL DIRECTION:
Headline Angle: {headline_angle}
Category: {category}
Reasoning for selection: {reasoning}

{author_context}

SOURCE POST(S):
{source_posts}

WRITING GUIDELINES:

1. **Headline**: Create a compelling, professional news headline (max 100 characters). It should be informative, not clickbait.

2. **Subheadline**: A one-sentence expansion that adds context (max 150 characters).

3. **Summary**: 2-3 sentences capturing the key takeaway for busy readers.

4. **Article Body** (400-700 words):
   - **Opening paragraph**: Lead with the most important fact or development. Answer: What happened? Who is involved? Why does it matter?
   - **Context & Background**: Provide relevant context about the company/person, the sector, and Kurdistan's business landscape
   - **Analysis & Implications**: What does this mean for the broader ecosystem? Connect to trends.
   - **Supporting Details**: Include relevant data points, engagement metrics, or quotes from the original post
   - **Forward-Looking Close**: End with implications, next steps, or what to watch for

5. **Tone**: Professional, authoritative, and informative — like Bloomberg or TechCrunch, but focused on Kurdistan Region. Avoid:
   - Overly casual language
   - Excessive praise or criticism
   - Speculative claims without marking them as such
   - Direct copy-paste from the LinkedIn post

6. **Attribution**: Always credit the original LinkedIn post author naturally within the text (e.g., "According to [Name], [role]..." or "[Name] shared on LinkedIn that...")

Respond with a JSON object:
{{
    "headline": "The article headline",
    "subheadline": "The subheadline",
    "summary": "2-3 sentence summary",
    "body_markdown": "The full article body in Markdown format",
    "category": "{category}",
    "tags": ["tag1", "tag2", "tag3"],
    "reading_time_minutes": 3,
    "author_attribution": "Based on a post by [Author Name], [Role/Company]",
    "key_quote": "A notable direct quote from the source post, if available"
}}

Respond ONLY with the JSON object."""


class ArticleWriter:
    """Generates detailed articles from selected post topics."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"
        self._memory_context_fn = None

    def set_memory_context_fn(self, fn):
        """Set a function that returns memory context for an author name."""
        self._memory_context_fn = fn

    def write_article(self, selection: dict) -> dict | None:
        """
        Write a single article from a selection dict containing source posts.
        """
        source_posts = selection.get("source_posts", [])
        if not source_posts:
            logger.warning("No source posts for article writing")
            return None

        # Format source posts for the prompt
        formatted_sources = []
        for sp in source_posts:
            post = sp.get("post", {})
            labels = sp.get("labels", {})
            formatted_sources.append(
                f"--- Post by {post.get('author_name', 'Unknown')} "
                f"({post.get('author_headline', '')}) ---\n"
                f"Content: {post.get('content_text') or post.get('text', '')}\n"
                f"Engagement: {post.get('likes_count', 0)} likes, "
                f"{post.get('comments_count', 0)} comments\n"
                f"AI Summary: {labels.get('summary', 'N/A') if labels else 'N/A'}\n"
                f"Business Impact: {labels.get('business_impact', 'N/A') if labels else 'N/A'}\n"
            )

        # Gather author context from memory
        author_context = ""
        if self._memory_context_fn:
            seen_authors = set()
            context_parts = []
            for sp in source_posts:
                post = sp.get("post", {})
                name = post.get("author_name", "")
                if name and name not in seen_authors:
                    seen_authors.add(name)
                    ctx = self._memory_context_fn(name)
                    if ctx:
                        context_parts.append(ctx)
            if context_parts:
                author_context = "AUTHOR BACKGROUND (use for richer context, NOT to share private details):\n" + "\n\n".join(context_parts)

        prompt = WRITER_PROMPT.format(
            headline_angle=selection.get("headline_angle", ""),
            category=selection.get("category", "General"),
            reasoning=selection.get("reasoning", ""),
            source_posts="\n\n".join(formatted_sources),
            author_context=author_context,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

            article = json.loads(result_text)
            article["rank"] = selection.get("rank", 0)
            article["source_selection"] = selection

            logger.info(f"Wrote article: {article.get('headline', 'untitled')}")
            return article

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse article JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error writing article: {e}")
            return None

    def write_batch(self, selections: list[dict]) -> list[dict]:
        """Write articles for all selections."""
        articles = []
        for i, sel in enumerate(selections):
            logger.info(f"Writing article {i + 1}/{len(selections)}...")
            article = self.write_article(sel)
            if article:
                articles.append(article)
        logger.info(f"Successfully wrote {len(articles)}/{len(selections)} articles")
        return articles
