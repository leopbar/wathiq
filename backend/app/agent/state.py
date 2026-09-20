"""The state that flows through the graph.

LangGraph passes one dictionary from node to node. Using a TypedDict (not a free-form dict)
means the editor and the type checker know what is in it, and a typo becomes an error instead
of a silently missing key.

Rule for this state: it holds only plain JSON-serialisable values. It is written to the
PostgreSQL checkpointer after every node, so a case can wait hours for a reviewer and then
carry on exactly where it stopped — possibly in a different process.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, TypedDict

NodeName = Literal["ocr", "classify", "extract", "validate", "review_gate", "finalize"]


def keep_last(_old: Any, new: Any) -> Any:
    """Reducer: the newest write wins. Explicit so parallel writes in M3 stay predictable."""
    return new


def extend(old: list[Any] | None, new: list[Any] | None) -> list[Any]:
    """Reducer: append instead of overwrite, so parallel workers (M3) can all contribute."""
    return [*(old or []), *(new or [])]


class DocumentState(TypedDict):
    """One document as the graph sees it."""

    document_id: str
    filename: str
    mime_type: str
    storage_path: str
    doc_type: str
    classification_confidence: float
    ocr_text: str
    ocr_confidence: float
    page_count: int
    language: str


class FieldState(TypedDict):
    """One extracted field, before it is written to the database."""

    name: str
    label_en: str
    label_ar: str
    value: str | None
    confidence: float
    is_critical: bool
    document_id: str | None
    page: NotRequired[int | None]
    bbox: NotRequired[list[float] | None]
    source_text: NotRequired[str | None]
    order_index: int


class FindingState(TypedDict):
    """A rule that fired."""

    code: str
    severity: str
    title: str
    description: str
    policy_citation: str | None


class CaseState(TypedDict):
    """Everything the graph knows about one case."""

    # --- identity (set once, never changed) ---
    case_id: str
    thread_id: str
    case_type: str

    # --- produced by the nodes ---
    documents: Annotated[list[DocumentState], keep_last]
    fields: Annotated[list[FieldState], extend]
    findings: Annotated[list[FindingState], extend]

    # --- routing and bookkeeping ---
    needs_review: NotRequired[bool]
    review_reasons: Annotated[list[dict[str, str]], extend]
    confidence: NotRequired[float]
    straight_through: NotRequired[bool]
    decision: NotRequired[str | None]
    corrections: NotRequired[dict[str, str]]
    error: NotRequired[str | None]
    prompt_versions: NotRequired[dict[str, str]]
