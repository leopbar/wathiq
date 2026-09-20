"""Building and searching the policy index.

The index is a table in the same PostgreSQL database as everything else, using pgvector. Three
operations:

* `rebuild` — chunk the corpus, embed each chunk, write it. Idempotent: it replaces the whole
  index, so a changed policy file or a changed embedder is one call away from consistent.
* `search` — nearest chunks to a query, by cosine distance, computed in the database.
* `by_citation` — the direct look-up, which is what a rule with a citation actually uses.

Why both: a rule pack already names its policy section, so quoting it is a look-up, not a
search, and a look-up cannot retrieve the wrong section. Search is for the cases that have no
citation — a guardrail finding, a reviewer asking "what covers this?" — where being
approximately right is better than saying nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.rag.chunking import load_corpus
from app.rag.embedder import get_embedder

logger = logging.getLogger(__name__)

# Below this similarity the nearest chunk is not really about the query, and quoting it would
# be worse than quoting nothing.
MIN_SIMILARITY = 0.12


@dataclass(slots=True)
class Retrieved:
    citation: str
    policy_id: str
    policy_title: str
    section: str
    heading: str
    text: str
    similarity: float

    @property
    def quote(self) -> str:
        """A short quotation for the findings panel — the first two sentences."""
        sentences = [part.strip() for part in self.text.replace("\n", " ").split(". ") if part]
        quote = ". ".join(sentences[:2]).strip()
        if quote and not quote.endswith("."):
            quote += "."
        return quote

    def as_dict(self) -> dict[str, object]:
        return {
            "citation": self.citation,
            "policy_id": self.policy_id,
            "policy_title": self.policy_title,
            "section": self.section,
            "heading": self.heading,
            "quote": self.quote,
            "similarity": self.similarity,
        }


async def rebuild(db: AsyncSession) -> int:
    """Re-chunk, re-embed and replace the whole index. Returns the number of chunks."""
    embedder = get_embedder()
    chunks = load_corpus()
    await db.execute(delete(models.PolicyChunk))
    for chunk in chunks:
        db.add(
            models.PolicyChunk(
                policy_id=chunk.policy_id,
                policy_title=chunk.policy_title,
                section=chunk.section,
                citation=chunk.citation,
                heading=chunk.heading,
                text=chunk.text,
                embedding=embedder.embed(chunk.embedding_text),
                embedder_version=embedder.version,
            )
        )
    await db.flush()
    logger.info("policy index rebuilt: %d chunk(s) with %s", len(chunks), embedder.version)
    return len(chunks)


async def is_indexed(db: AsyncSession) -> bool:
    row = (await db.execute(select(models.PolicyChunk.id).limit(1))).first()
    return row is not None


def _to_retrieved(row: models.PolicyChunk, similarity: float) -> Retrieved:
    return Retrieved(
        citation=row.citation,
        policy_id=row.policy_id,
        policy_title=row.policy_title,
        section=row.section,
        heading=row.heading,
        text=row.text,
        similarity=round(similarity, 4),
    )


async def by_citation(db: AsyncSession, citation: str) -> Retrieved | None:
    """The exact section a rule cites. No search, no approximation."""
    row = (
        await db.execute(
            select(models.PolicyChunk).where(models.PolicyChunk.citation == citation.strip())
        )
    ).scalar_one_or_none()
    return _to_retrieved(row, 1.0) if row else None


async def search(db: AsyncSession, query: str, limit: int = 3) -> list[Retrieved]:
    """Nearest policy sections to a piece of text, by cosine distance in pgvector."""
    vector = get_embedder().embed(query)
    if not any(vector):
        return []

    distance = models.PolicyChunk.embedding.cosine_distance(vector)
    rows = (
        await db.execute(
            select(models.PolicyChunk, distance.label("distance"))
            .order_by(distance)
            .limit(max(1, min(limit, 20)))
        )
    ).all()

    results = []
    for row, raw_distance in rows:
        # pgvector returns a distance; 1 - distance is the cosine similarity.
        similarity = 1.0 - float(raw_distance)
        if similarity >= MIN_SIMILARITY:
            results.append(_to_retrieved(row, similarity))
    return results


async def cite(db: AsyncSession, citation: str | None, fallback_query: str) -> Retrieved | None:
    """What a finding gets: the cited section if it has one, else the nearest match."""
    if citation:
        found = await by_citation(db, citation)
        if found is not None:
            return found
    results = await search(db, fallback_query, limit=1)
    return results[0] if results else None
