"""
AI article editor that reviews, refines, and ensures quality of generated articles.
Acts as a copy editor and fact-checker relative to source material.
"""

import json
import logging
import re

import anthropic
import markdown

from backend.config import settings

logger = logging.getLogger(__name__)


EDITOR_PROMPT = """You are a meticulous senior editor at "Kurdistan Business Insight", a premium business news platform.

Review and edit the following article draft. Your role is to ensure it meets the highest editorial standards.

ARTICLE DRAFT:
Headline: {headline}
Subheadline: {subheadline}
Category: {category}

Body:
{body_markdown}

ORIGINAL SOURCE MATERIAL (for fact-checking):
{source_summary}

EDITORIAL CHECKLIST:
1. **Accuracy**: Does the article accurately reflect the source material? Flag any claims not supported by the source.
2. **Headline Quality**: Is the headline compelling, accurate, and professional? Not clickbait?
3. **Structure**: Does it follow inverted pyramid (most important info first)?
4. **Clarity**: Is the writing clear, concise, and jargon-free where possible?
5. **Tone**: Professional and authoritative, appropriate for Kurdistan's business community?
6. **Attribution**: Is the source properly credited?
7. **Grammar & Style**: Correct grammar, consistent style, proper punctuation?
8. **Length**: Is it appropriately detailed (400-700 words) without padding?
9. **Business Value**: Does it offer genuine insight for business readers?

Respond with a JSON object:
{{
    "headline": "The final edited headline (modify if needed)",
    "subheadline": "The final edited subheadline",
    "summary": "Refined 2-3 sentence summary",
    "body_markdown": "The fully edited article body in Markdown",
    "body_html": "The article body converted to clean HTML",
    "editorial_notes": "Brief notes on what was changed and why",
    "quality_score": 8.5,
    "reading_time_minutes": 3,
    "tags": ["updated", "tags", "if needed"],
    "category": "{category}"
}}

The quality_score should be 1-10 based on the final edited version.
The body_html should use semantic HTML tags: <p>, <h2>, <h3>, <strong>, <em>, <blockquote>, <ul>, <li>.

Respond ONLY with the JSON object."""


class ArticleEditor:
    """Reviews and edits AI-generated articles for quality."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    def edit_article(self, article: dict) -> dict | None:
        """
        Edit and review a single article.
        Returns the edited article with HTML body and quality score.
        """
        source_selection = article.get("source_selection", {})
        source_posts = source_selection.get("source_posts", [])

        # Build source summary for fact-checking
        source_summaries = []
        for sp in source_posts:
            post = sp.get("post", {})
            content = post.get("content_text") or post.get("text") or ""
            source_summaries.append(
                f"- {post.get('author_name', 'Unknown')}: {content[:300]}"
            )

        prompt = EDITOR_PROMPT.format(
            headline=article.get("headline", ""),
            subheadline=article.get("subheadline", ""),
            category=article.get("category", "General"),
            body_markdown=article.get("body_markdown", ""),
            source_summary="\n".join(source_summaries) if source_summaries else "No source available",
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

            edited = json.loads(result_text)

            # Merge with original article data
            edited["rank"] = article.get("rank", 0)
            edited["source_selection"] = source_selection
            edited["author_attribution"] = article.get("author_attribution", "")
            edited["key_quote"] = article.get("key_quote", "")

            # Generate HTML from markdown if not provided or poor quality
            if not edited.get("body_html"):
                edited["body_html"] = markdown.markdown(
                    edited.get("body_markdown", ""),
                    extensions=["extra", "smarty"],
                )

            logger.info(
                f"Edited article: {edited.get('headline')} "
                f"(quality: {edited.get('quality_score', 'N/A')})"
            )
            return edited

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse editor response: {e}")
            # Return original with basic HTML conversion
            article["body_html"] = markdown.markdown(
                article.get("body_markdown", ""),
                extensions=["extra", "smarty"],
            )
            article["quality_score"] = 5.0
            return article
        except Exception as e:
            logger.error(f"Error editing article: {e}")
            article["body_html"] = markdown.markdown(
                article.get("body_markdown", ""),
                extensions=["extra", "smarty"],
            )
            article["quality_score"] = 5.0
            return article

    def edit_batch(self, articles: list[dict]) -> list[dict]:
        """Edit all articles and sort by quality."""
        edited = []
        for i, article in enumerate(articles):
            logger.info(f"Editing article {i + 1}/{len(articles)}...")
            result = self.edit_article(article)
            if result:
                edited.append(result)

        # Sort by quality score descending
        edited.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        logger.info(f"Edited {len(edited)}/{len(articles)} articles")
        return edited
