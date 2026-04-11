"""
Article deduplication system.

Two layers:
  1. Intra-batch: After selection, detect and remove near-duplicate articles
     within the same day's batch using embedding similarity.
  2. Cross-day: Feed the selector a list of recently published headlines
     so it avoids repeating stories from previous days.
"""

import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from backend.database.models import Article
from backend.processing.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)

# Two articles with cosine similarity above this threshold are considered duplicates
SIMILARITY_THRESHOLD = 0.55


def get_recent_headlines(db: Session, days: int = 7, limit: int = 60) -> list[str]:
    """
    Get headlines of recently published articles for cross-day dedup.
    Returns a list of headline strings the selector should avoid repeating.
    """
    cutoff = date.today() - timedelta(days=days)
    articles = (
        db.query(Article.headline, Article.summary)
        .filter(Article.is_published == True, Article.publish_date >= cutoff)
        .order_by(Article.publish_date.desc())
        .limit(limit)
        .all()
    )
    return [f"{a.headline} — {a.summary[:100]}" for a in articles if a.headline]


def deduplicate_selections(
    selections: list[dict],
    processed_posts: list[dict],
    embedder: Optional[EmbeddingEngine] = None,
) -> list[dict]:
    """
    Remove near-duplicate selections from a batch.
    Uses embedding similarity on the headline_angle + source content.

    Returns deduplicated list, preserving rank order.
    """
    if len(selections) <= 1:
        return selections

    if embedder is None:
        embedder = EmbeddingEngine()

    # Build text representation for each selection
    texts = []
    for sel in selections:
        parts = [sel.get("headline_angle", ""), sel.get("category", "")]
        # Add source post summaries
        for sp in sel.get("source_posts", []):
            labels = sp.get("labels", {})
            if labels:
                parts.append(labels.get("summary", ""))
            post = sp.get("post", {})
            content = post.get("content_text") or post.get("text") or ""
            parts.append(content[:300])
        texts.append(" ".join(parts))

    # Generate embeddings
    embeddings = embedder.generate_batch_embeddings(texts)
    if not embeddings or len(embeddings) < 2:
        return selections

    # Compute pairwise cosine similarity
    sim_matrix = cosine_similarity(np.array(embeddings))

    # Mark duplicates — keep the higher-ranked (earlier) one
    to_remove = set()
    for i in range(len(selections)):
        if i in to_remove:
            continue
        for j in range(i + 1, len(selections)):
            if j in to_remove:
                continue
            if sim_matrix[i][j] >= SIMILARITY_THRESHOLD:
                # Remove the lower-ranked (later) one
                to_remove.add(j)
                logger.info(
                    f"Dedup: Removing selection #{j+1} (sim={sim_matrix[i][j]:.2f}) — "
                    f"too similar to #{i+1}: "
                    f"\"{selections[i].get('headline_angle', '')[:50]}\" ≈ "
                    f"\"{selections[j].get('headline_angle', '')[:50]}\""
                )

    deduped = [s for i, s in enumerate(selections) if i not in to_remove]
    removed = len(selections) - len(deduped)

    if removed > 0:
        logger.info(f"Dedup: Removed {removed} duplicate selections, {len(deduped)} remaining")

    return deduped


def deduplicate_against_published(
    selections: list[dict],
    db: Session,
    embedder: Optional[EmbeddingEngine] = None,
    days: int = 7,
) -> list[dict]:
    """
    Remove selections that are too similar to recently published articles.
    """
    recent = get_recent_headlines(db, days=days)
    if not recent or not selections:
        return selections

    if embedder is None:
        embedder = EmbeddingEngine()

    # Embed published headlines
    published_texts = recent
    published_embeddings = embedder.generate_batch_embeddings(published_texts)

    # Embed current selections
    sel_texts = []
    for sel in selections:
        parts = [sel.get("headline_angle", ""), sel.get("category", "")]
        for sp in sel.get("source_posts", []):
            labels = sp.get("labels", {})
            if labels:
                parts.append(labels.get("summary", ""))
        sel_texts.append(" ".join(parts))

    sel_embeddings = embedder.generate_batch_embeddings(sel_texts)

    if not published_embeddings or not sel_embeddings:
        return selections

    # Check each selection against published articles
    sim_matrix = cosine_similarity(
        np.array(sel_embeddings), np.array(published_embeddings)
    )

    to_remove = set()
    for i in range(len(selections)):
        max_sim = float(np.max(sim_matrix[i]))
        if max_sim >= SIMILARITY_THRESHOLD:
            best_match_idx = int(np.argmax(sim_matrix[i]))
            to_remove.add(i)
            logger.info(
                f"Dedup (cross-day): Removing \"{selections[i].get('headline_angle', '')[:50]}\" "
                f"(sim={max_sim:.2f}) — similar to published: \"{recent[best_match_idx][:60]}\""
            )

    deduped = [s for i, s in enumerate(selections) if i not in to_remove]
    removed = len(selections) - len(deduped)

    if removed > 0:
        logger.info(f"Cross-day dedup: Removed {removed}, {len(deduped)} remaining")

    return deduped
