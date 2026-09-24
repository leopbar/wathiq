"""The state that flows through the graph.

LangGraph passes one dictionary from node to node. Using a TypedDict (not a free-form dict)
means the editor and the type checker know what is in it, and a typo becomes an error instead
of a silently missing key.

Rule for this state: it holds only plain JSON-serialisable values. It is written to the
PostgreSQL checkpointer after every node, so a case can wait hours for a reviewer and then
carry on exactly where it stopped — possibly in a different process.

**Reducers matter here.** Since M3 the extraction workers run in parallel, one per document,
and several of them write to the state in the same superstep. A key whose reducer is
`keep_last` would lose all but one of those writes. Every key a worker touches therefore uses
`extend`, which appends, or `merge_fields`, which appends new fields and replaces ones that
are already there — that is how the critic can revise a field without duplicating it.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, TypedDict

NodeName = Literal[
    "ocr",
    "guardrails",
    "supervisor",
    "extract_worker",
    "critic",
    "investigator",
    "validate",
    "review_gate",
    "finalize",
]


def keep_last(_old: Any, new: Any) -> Any:
    """Reducer: the newest write wins. Explicit so parallel writes stay predictable."""
    return new


def extend(old: list[Any] | None, new: list[Any] | None) -> list[Any]:
    """Reducer: append instead of overwrite, so the parallel workers can all contribute."""
    return [*(old or []), *(new or [])]


def merge(old: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer for dictionaries: later keys win, earlier keys survive."""
    return {**(old or {}), **(new or {})}


def merge_fields(old: list[Any] | None, new: list[Any] | None) -> list[Any]:
    """Reducer for `fields`: append new fields, replace ones already there.

    The parallel workers each write the fields of their own document, so they never collide.
    The critic then writes updated copies of fields it has looked at, and those must *replace*
    rather than duplicate. Identity is (document, field name), and the result stays sorted by
    the order the schema defines so the UI does not shuffle between runs.
    """
    merged: dict[tuple[str, str], Any] = {
        (str(item.get("document_id") or ""), str(item["name"])): item for item in (old or [])
    }
    for item in new or []:
        merged[(str(item.get("document_id") or ""), str(item["name"]))] = item
    return sorted(merged.values(), key=lambda item: item.get("order_index", 0))


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
    # Set by the guardrails node: the cleaned text the pipeline reads — invisible characters
    # and markup removed, values intact. NOT the PII-tokenised copy, which exists only for
    # logs. The original stays in `ocr_text` for the reviewer.
    safe_text: NotRequired[str]
    # Where each line sat on the page, when the OCR engine reported geometry (M6, Document
    # Intelligence). `[{text, page, bbox, confidence}]`; empty for the demo reader. This is
    # what lets a field carry a highlight box and its own read confidence.
    line_boxes: NotRequired[list[dict[str, Any]]]


class FieldState(TypedDict):
    """One extracted field, before it is written to the database."""

    name: str
    label_en: str
    label_ar: str
    value: str | None
    # A reading aid, never the value: the English of an Arabic value, with where it came from
    # ("glossary", "model" or "none"). The audit trail and the posting use `value`.
    value_translated: NotRequired[str | None]
    translation_source: NotRequired[str]
    # The weighted score built from the signals below.
    confidence: float
    # `confidence` passed through the calibration curve. Equal to it when not yet calibrated.
    calibrated_confidence: NotRequired[float]
    # What the score was built from, so the UI can explain it: [{key,label,value,weight,detail}]
    signals: NotRequired[list[dict[str, Any]]]
    is_critical: bool
    document_id: str | None
    page: NotRequired[int | None]
    bbox: NotRequired[list[float] | None]
    source_text: NotRequired[str | None]
    # How many extraction attempts the worker needed before the value validated.
    attempts: NotRequired[int]
    # The critic's verdict on this field: {agreed, reason, via, suggested_value}
    critic: NotRequired[dict[str, Any] | None]
    order_index: int


class FindingState(TypedDict):
    """A rule that fired, or something the investigator established."""

    code: str
    severity: str
    title: str
    description: str
    policy_citation: str | None
    policy_quote: NotRequired[str | None]
    source: NotRequired[str]


class WorkerResult(TypedDict):
    """What one parallel extraction worker produced for one document."""

    document_id: str
    filename: str
    doc_type: str
    field_count: int
    attempts: int
    repairs: list[dict[str, str]]
    examples: list[dict[str, Any]]
    prompt_version: str
    model_version: str
    duration_ms: int


class CaseState(TypedDict):
    """Everything the graph knows about one case."""

    # --- identity (set once, never changed) ---
    case_id: str
    thread_id: str
    case_type: str

    # --- produced by the nodes ---
    documents: Annotated[list[DocumentState], keep_last]
    fields: Annotated[list[FieldState], merge_fields]
    findings: Annotated[list[FindingState], extend]

    # --- M3: assurance evidence ---
    # One guardrail report per document, from the guardrails node.
    guardrails: Annotated[list[dict[str, Any]], extend]
    # One entry per parallel worker. Written concurrently, hence the append reducer.
    worker_results: Annotated[list[WorkerResult], extend]
    # The critic's notes, and the investigator's thought/action/observation trail.
    critic_notes: Annotated[list[dict[str, Any]], extend]
    investigation: Annotated[list[dict[str, Any]], extend]
    # Every MCP tool call the case made, in order, with its result.
    tool_calls: Annotated[list[dict[str, Any]], extend]
    # The supervisor's plan: which document goes to which worker, and why.
    plan: NotRequired[list[dict[str, Any]]]

    # --- routing and bookkeeping ---
    needs_review: NotRequired[bool]
    review_reasons: Annotated[list[dict[str, str]], extend]
    confidence: NotRequired[float]
    straight_through: NotRequired[bool]
    decision: NotRequired[str | None]
    corrections: NotRequired[dict[str, str]]
    error: NotRequired[str | None]
    prompt_versions: NotRequired[dict[str, str]]
    # Which rule pack version judged this case, per document type.
    rule_packs: NotRequired[dict[str, str]]
    # Whether the confidence figures on this case went through a fitted curve.
    calibration: NotRequired[dict[str, Any]]


class WorkerInput(TypedDict):
    """The payload a `Send` hands to one extraction worker.

    Deliberately small: a worker gets one document and the schema for it, not the whole case.
    """

    case_id: str
    document: DocumentState
    field_schema: list[dict[str, Any]]
    order_offset: int
    prompt_version: str
    # The text of that prompt version (M6). Loaded once by the supervisor rather than by each
    # worker, so a model-backed extractor never has to reach into the database itself. Empty
    # in demo mode, where the extractor makes no model call and the wording cannot matter.
    prompt_body: NotRequired[str]
