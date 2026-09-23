"""Turning text into a vector.

DEMO mode uses `HashingEmbedder`: a hashed lexical embedding, sometimes called the hashing
trick. Every word and every word pair in the text is hashed into one of 256 buckets, the
buckets are weighted, and the vector is normalised to unit length. Cosine similarity between
two of these vectors is then a measure of how much vocabulary two pieces of text share.

It is honest about what it is: a **lexical** embedding, not a semantic one. It will match
"expired trade licence" to a policy section about expired licences, because the words overlap.
It will not know that "lapsed" means the same thing. For retrieving a policy section by the
words in a finding, that is enough, and it costs no model call, no network and no GPU — which
is what lets the whole demo run offline and reproducibly.

AZURE mode (M6) plugs an Azure OpenAI embedding deployment in behind this same interface. The
chunking, the index, the search and the citation all stay exactly as they are; only the vectors
change. The dimension is a property of the backend, so the migration for a real embedding model
is a re-index, not a rewrite.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from itertools import pairwise

# Small enough to keep the index tiny, large enough that unrelated words rarely collide.
DEMO_DIMENSIONS = 256

_TOKEN = re.compile(r"[a-z0-9§]+")
# Words that appear in every policy section and therefore say nothing about which one it is.
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "before", "by", "for", "from",
        "has", "have", "in", "is", "it", "its", "must", "no", "not", "of", "on", "or",
        "that", "the", "this", "to", "was", "were", "which", "who", "will", "with",
        "where", "whose", "than", "then", "they", "their", "these",
    }
)


def tokenise(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(text.lower()) if token not in _STOPWORDS]


def _bucket(token: str, dimensions: int) -> int:
    """A stable bucket for a token.

    `blake2b`, not Python's `hash()`: `hash()` is randomised per process, so the same text
    would embed differently after a restart and the index would silently rot.
    """
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimensions


class Embedder(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @property
    @abstractmethod
    def label(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    def embed_all(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class HashingEmbedder(Embedder):
    """Hashed lexical embedding. Deterministic, offline, no model."""

    def __init__(self, dimensions: int = DEMO_DIMENSIONS) -> None:
        self._dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        tokens = tokenise(text)
        if not tokens:
            return [0.0] * self._dimensions

        counts: dict[int, float] = {}
        for token in tokens:
            counts[_bucket(token, self._dimensions)] = (
                counts.get(_bucket(token, self._dimensions), 0.0) + 1.0
            )
        # Word pairs, at half weight: they carry the phrase "expiry date" as something more
        # than the two words separately, which matters for short policy sections.
        for left, right in pairwise(tokens):
            bucket = _bucket(f"{left}_{right}", self._dimensions)
            counts[bucket] = counts.get(bucket, 0.0) + 0.5

        vector = [0.0] * self._dimensions
        for bucket, count in counts.items():
            # Sub-linear term frequency: a word repeated ten times is not ten times as
            # important as a word seen once.
            vector[bucket] = 1.0 + math.log(count)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [round(value / norm, 6) for value in vector]

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def label(self) -> str:
        return "Demo embedder (hashed lexical vectors, no model call)"

    @property
    def version(self) -> str:
        return f"demo-hashing-1.0.0-d{self._dimensions}"


def cosine(left: list[float], right: list[float]) -> float:
    """Both vectors are unit length, so this is just the dot product."""
    return round(sum(a * b for a, b in zip(left, right, strict=False)), 6)


_backend: Embedder | None = None


def get_embedder() -> Embedder:
    """The embedder this deployment is configured for.

    Azure only when an embedding deployment is named, which is separate from the chat
    deployment: running a real extractor against the hashed lexical index is a legitimate
    intermediate state, and this is what makes it expressible. The import is inside the branch
    so demo mode never loads an Azure SDK.
    """
    global _backend
    if _backend is None:
        from app.core.config import settings

        if settings.foundry_enabled and settings.azure_openai_embedding_deployment.strip():
            from app.azure.foundry import FoundryEmbedder

            _backend = FoundryEmbedder()
        else:
            _backend = HashingEmbedder()
    return _backend


def reset_embedder() -> None:
    """Drop the cached backend so a test can change the settings and pick a different one.

    Note for anyone switching embedders in a running system: the stored vectors were produced
    by whichever embedder was active when the index was built, and vectors from two different
    models are not comparable. Changing this means re-running `rag.index.rebuild()`.
    """
    global _backend
    _backend = None
