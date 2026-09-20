"""Choosing few-shot examples for an extraction prompt.

A prompt that shows the model two or three worked examples extracts better than one that shows
none — but only if the examples resemble the document in front of it. Sending the same fixed
examples every time wastes tokens on an irrelevant layout; sending *all* of them costs money
and eventually confuses the model.

So the examples are stored with an embedding, and the ones nearest the document being read are
selected. Same embedder as the policy index, same idea, different corpus.

**Honesty note.** In demo mode the extractor is deterministic and makes no model call, so the
selected examples are not sent anywhere. The selection still runs, and which examples it chose
is recorded on the case, because the *selection* is the mechanism being demonstrated and it is
what Azure mode (M6) hands to the model. The UI says "selected for the prompt (no model call in
demo mode)" rather than implying the examples influenced the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.rag.embedder import cosine, get_embedder

EXAMPLE_DIR = Path(__file__).parent / "examples"


@dataclass(slots=True)
class Example:
    id: str
    doc_type: str
    note: str
    text: str
    expected: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "doc_type": self.doc_type, "note": self.note}


@dataclass(slots=True)
class Selection:
    example: Example
    similarity: float

    def as_dict(self) -> dict[str, Any]:
        return {**self.example.as_dict(), "similarity": self.similarity}


_examples: list[Example] | None = None
_vectors: dict[str, list[float]] = {}


def load_examples() -> list[Example]:
    """Read the example bank from disk once, and embed each example."""
    global _examples
    if _examples is not None:
        return _examples

    embedder = get_embedder()
    examples: list[Example] = []
    if EXAMPLE_DIR.is_dir():
        for path in sorted(EXAMPLE_DIR.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for item in raw.get("examples", []):
                example = Example(
                    id=str(item["id"]),
                    doc_type=str(raw.get("doc_type", path.stem)),
                    note=str(item.get("note", "")),
                    text=str(item.get("text", "")),
                    expected={str(k): str(v) for k, v in (item.get("expected") or {}).items()},
                )
                examples.append(example)
                _vectors[example.id] = embedder.embed(example.text)
    _examples = examples
    return examples


def select(doc_type: str, document_text: str, k: int = 2) -> list[Selection]:
    """The `k` examples of this document type most like the document being read."""
    candidates = [example for example in load_examples() if example.doc_type == doc_type]
    if not candidates:
        return []

    query = get_embedder().embed(document_text)
    if not any(query):
        return [Selection(example=example, similarity=0.0) for example in candidates[:k]]

    scored = [
        Selection(example=example, similarity=cosine(query, _vectors[example.id]))
        for example in candidates
    ]
    scored.sort(key=lambda selection: selection.similarity, reverse=True)
    return scored[: max(0, k)]


def reload() -> None:
    """Drop the cache. Tests use this; there is no hot reload in production."""
    global _examples
    _examples = None
    _vectors.clear()
