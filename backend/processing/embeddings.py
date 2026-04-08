"""
Embedding generation and similarity clustering for processed posts.
Uses sentence-transformers for local embedding generation.
"""

import logging
from typing import Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Generates embeddings and clusters similar posts."""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model...")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded.")
        return self._model

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a text string."""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, normalize_embeddings=True, batch_size=32)
        return embeddings.tolist()

    def build_post_text(self, post_data: dict, labels: Optional[dict] = None) -> str:
        """
        Build a composite text representation of a post for embedding.
        Combines content, summary, and metadata for richer representation.
        """
        parts = []

        author = post_data.get("author_name", "")
        if author:
            parts.append(f"Author: {author}")

        content = post_data.get("content_text") or post_data.get("text") or ""
        if content:
            parts.append(content[:1000])

        if labels:
            summary = labels.get("summary", "")
            if summary:
                parts.append(f"Summary: {summary}")
            category = labels.get("category", "")
            if category:
                parts.append(f"Category: {category}")
            tags = labels.get("tags", [])
            if tags:
                parts.append(f"Tags: {', '.join(tags)}")

        return "\n".join(parts)

    def cluster_posts(
        self,
        embeddings: list[list[float]],
        distance_threshold: float = 0.5,
    ) -> list[int]:
        """
        Cluster posts by similarity using agglomerative clustering.
        Returns cluster ID for each post.
        """
        if len(embeddings) < 2:
            return list(range(len(embeddings)))

        embedding_matrix = np.array(embeddings)

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="cosine",
            linkage="average",
        )

        cluster_ids = clustering.fit_predict(embedding_matrix)
        n_clusters = len(set(cluster_ids))
        logger.info(f"Clustered {len(embeddings)} posts into {n_clusters} groups")

        return cluster_ids.tolist()

    def find_similar_posts(
        self,
        target_embedding: list[float],
        all_embeddings: list[list[float]],
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[tuple[int, float]]:
        """
        Find the most similar posts to a target post.
        Returns list of (index, similarity_score) tuples.
        """
        if not all_embeddings:
            return []

        target = np.array(target_embedding).reshape(1, -1)
        matrix = np.array(all_embeddings)

        similarities = cosine_similarity(target, matrix)[0]

        # Filter by threshold and sort by similarity
        similar = [
            (i, float(sim))
            for i, sim in enumerate(similarities)
            if sim >= threshold
        ]
        similar.sort(key=lambda x: x[1], reverse=True)

        return similar[:top_k]
