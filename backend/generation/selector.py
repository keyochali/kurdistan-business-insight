"""
AI-powered topic selector that picks the top 20 most newsworthy stories
from the day's processed LinkedIn posts.
"""

import json
import logging

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)


SELECTION_PROMPT = """You are a senior editorial director for "Kurdistan Business Insight" — a premium daily business news platform covering the Kurdistan Region's business ecosystem.

You have {post_count} LinkedIn posts from today, scraped from prominent business leaders and companies in Kurdistan. Your job is to select exactly {article_count} posts (or groups of related posts) that will become today's featured articles.

{recently_published}

Here are all the processed posts with their metadata:

{posts_json}

SELECTION CRITERIA (in order of importance):

1. **NO DUPLICATES — THIS IS CRITICAL**: Each selected article MUST cover a distinctly different story. NEVER select two articles about the same company doing the same thing, the same partnership, the same event, or the same topic from a different angle. If 5 posts are about "Lezzoo hiring", that is ONE article, not two. If 3 posts mention "university partnerships", combine them into ONE article or pick only the most unique angle. One company = maximum ONE article about them, unless they have genuinely unrelated news.

2. **No Repetition of Recently Published Stories**: If RECENTLY PUBLISHED ARTICLES are listed above, do NOT select any story that covers the same topic, event, or company development. Find genuinely NEW angles.

3. **Genuine Business News**: Prioritize actual business developments — new investments, product launches, partnerships, expansions, policy changes, market insights, funding rounds.

4. **Maximum Diversity**: Spread selections across as many DIFFERENT companies, people, sectors, and topics as possible. If you have 20 slots, aim for 20 different companies/people — never give the same entity two articles.

5. **Author Authority**: Use author_authority_score (1-10) to weight importance — senior leaders and major companies get priority over junior professionals.

6. **Impact & Significance**: Choose stories that matter to the broader Kurdistan business ecosystem.

7. **Cluster Awareness**: Posts with the same cluster_id cover the same topic — select the cluster as ONE combined article, never as separate articles.

HARD RULES:
- Maximum 1 article per company/person (unless they have 2+ genuinely unrelated stories)
- Maximum 1 article per specific topic (e.g., "university partnerships" = 1 article, not 3)
- If multiple posts from the same company say similar things, merge into ONE selection with multiple post_ids
- Never create two articles that a reader would say "didn't I just read about this?"

AVOID selecting:
- Generic motivational or inspirational quotes
- Pure self-promotion without substance
- Reshares without original commentary
- Posts with very little content
- Any topic already covered in recently published articles

Respond with a JSON array of exactly {article_count} selections:
[
    {{
        "rank": 1,
        "post_ids": [1],
        "headline_angle": "Proposed headline angle for the article",
        "category": "Technology",
        "reasoning": "Brief explanation of why this was selected and how it differs from other selections",
        "related_post_ids": [2, 5]
    }},
    ...
]

If there are fewer than {article_count} UNIQUE newsworthy stories, return fewer articles rather than padding with duplicates or weak content. Quality and uniqueness over quantity.

Respond ONLY with the JSON array."""


class ArticleSelector:
    """Selects the top stories to become articles from processed posts."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"
        self._authority_scores = {}

    def set_authority_scores(self, scores: dict):
        """Set {name: score} dict from memory system."""
        self._authority_scores = scores or {}

    def _get_authority(self, author_name: str) -> float:
        """Lookup authority score for an author, fuzzy match."""
        if author_name in self._authority_scores:
            return self._authority_scores[author_name]
        first = author_name.split()[0].lower() if author_name else ""
        for name, score in self._authority_scores.items():
            if first and first in name.lower():
                return score
        return 5.0

    def set_recent_headlines(self, headlines: list[str]):
        """Set recently published headlines for cross-day dedup."""
        self._recent_headlines = headlines

    def select_articles(
        self,
        processed_posts: list[dict],
        article_count: int = None,
    ) -> list[dict]:
        """
        Select the top N most newsworthy posts/topics from processed posts.
        Returns list of selection dicts with post references and metadata.
        """
        if article_count is None:
            article_count = settings.daily_article_count

        if not processed_posts:
            logger.warning("No processed posts to select from")
            return []

        # Build condensed post summaries for the selector
        posts_for_selection = []
        for i, pp in enumerate(processed_posts):
            post = pp.get("post", {})
            labels = pp.get("labels", {})
            if labels is None:
                continue

            author_name = post.get("author_name", "Unknown")
            posts_for_selection.append({
                "id": i,
                "author": author_name,
                "author_authority_score": self._get_authority(author_name),
                "content_preview": (post.get("content_text") or post.get("text") or "")[:500],
                "summary": labels.get("summary", ""),
                "category": labels.get("category", ""),
                "tags": labels.get("tags", []),
                "newsworthiness_score": labels.get("newsworthiness_score", 0),
                "news_angle": labels.get("news_angle", ""),
                "business_impact": labels.get("business_impact", ""),
                "is_promotional": labels.get("is_promotional", False),
                "engagement": {
                    "likes": post.get("likes_count", 0),
                    "comments": post.get("comments_count", 0),
                },
                "cluster_id": pp.get("cluster_id"),
            })

        # Sort by newsworthiness before sending to AI
        posts_for_selection.sort(
            key=lambda x: x.get("newsworthiness_score", 0), reverse=True
        )

        # Take top 60 to give the AI enough to work with but not too much
        candidates = posts_for_selection[:60]

        # Build recently-published section for cross-day dedup
        recent = getattr(self, "_recent_headlines", [])
        if recent:
            recent_text = "RECENTLY PUBLISHED ARTICLES (DO NOT repeat these topics):\n"
            for h in recent[:30]:
                recent_text += f"- {h}\n"
        else:
            recent_text = ""

        prompt = SELECTION_PROMPT.format(
            post_count=len(candidates),
            article_count=min(article_count, len(candidates)),
            posts_json=json.dumps(candidates, indent=2, default=str),
            recently_published=recent_text,
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

            selections = json.loads(result_text)

            # Enrich selections with full post data
            for sel in selections:
                sel["source_posts"] = []
                all_ids = sel.get("post_ids", []) + sel.get("related_post_ids", [])
                for pid in all_ids:
                    if 0 <= pid < len(processed_posts):
                        sel["source_posts"].append(processed_posts[pid])

            logger.info(f"Selected {len(selections)} articles from {len(candidates)} candidates")
            return selections

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse selection response: {e}")
            return self._fallback_selection(processed_posts, article_count)
        except Exception as e:
            logger.error(f"Error in article selection: {e}")
            return self._fallback_selection(processed_posts, article_count)

    def _fallback_selection(self, processed_posts: list[dict], count: int) -> list[dict]:
        """Fallback: select top posts by newsworthiness score."""
        logger.info("Using fallback selection by newsworthiness score")

        scored = []
        for i, pp in enumerate(processed_posts):
            labels = pp.get("labels")
            if labels is None:
                continue
            scored.append((i, labels.get("newsworthiness_score", 0), pp))

        scored.sort(key=lambda x: x[1], reverse=True)

        selections = []
        for rank, (idx, score, pp) in enumerate(scored[:count], 1):
            labels = pp.get("labels", {})
            selections.append({
                "rank": rank,
                "post_ids": [idx],
                "headline_angle": labels.get("news_angle", labels.get("summary", "")),
                "category": labels.get("category", "General"),
                "reasoning": f"Selected by newsworthiness score: {score}",
                "source_posts": [pp],
            })

        return selections
