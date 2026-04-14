"""Shared embedding helpers for Day 09 workers and indexing.

The helpers keep retrieval and setup_index aligned so the ChromaDB index
and query vectors always use the same dimension and normalization rules.
"""

from __future__ import annotations

import hashlib
import os
import random
import sys
from functools import lru_cache

EMBED_DIM = 1536
DEFAULT_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")


def _normalize(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _resize_vector(vector: list[float], target_dim: int = EMBED_DIM) -> list[float]:
    if len(vector) == target_dim:
        return vector
    if len(vector) > target_dim:
        return vector[:target_dim]
    repeats = (target_dim + len(vector) - 1) // len(vector)
    return (vector * repeats)[:target_dim]


def _stable_random_vector(text: str, target_dim: int = EMBED_DIM) -> list[float]:
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    return _normalize([rng.random() for _ in range(target_dim)])


@lru_cache(maxsize=1)
def get_embedding_fn():
    """Return a text -> vector callable.

    Priority:
    1. SentenceTransformer if installed
    2. OpenAI embeddings if OPENAI_API_KEY is available
    3. Deterministic random fallback (smoke test only)
    """
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
        model = SentenceTransformer(model_name)

        def embed(text: str) -> list[float]:
            vector = model.encode([text], normalize_embeddings=True)[0].tolist()
            return _resize_vector(vector)

        return embed
    except Exception:
        pass

    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and not api_key.startswith("sk-...your"):
            client = OpenAI(api_key=api_key)

            def embed(text: str) -> list[float]:
                response = client.embeddings.create(input=text, model=DEFAULT_MODEL)
                return _normalize(response.data[0].embedding)

            return embed
    except Exception as exc:
        print(f"⚠️  OpenAI embedding init failed: {exc}", file=sys.stderr)

    print(
        "⚠️  Using deterministic random embeddings. "
        "Install sentence-transformers or set OPENAI_API_KEY for higher quality retrieval.",
        file=sys.stderr,
    )
    return _stable_random_vector


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts with the shared embedding function."""
    embed = get_embedding_fn()
    return [embed(text) for text in texts]
