"""The graph nodes: one small, explainable step each.

Every node takes the state, does one job, and returns only the keys it changed. LangGraph
merges those keys into the state and checkpoints the result, so the case can stop and resume
between any two nodes.

The review gate is the one node with a hard rule: **it must not change anything before it
calls `interrupt()`**, because when a reviewer answers, LangGraph re-runs the node from the
top. Anything written before the interrupt would be written twice.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any
from uuid import UUID

from langgraph.types import interrupt
from sqlalchemy import select

from app.agent import rules as rule_engine
from app.agent.classifier import classify
from app.agent.extractor import get_extractor
from app.agent.ocr import get_ocr
from app.agent.state import CaseState, DocumentState, FieldState, FindingState
from app.db import models
from app.db.enums import ActorType, DocTypeKey, Severity
from app.db.session import SessionLocal
from app.services.events import record_event
from app.services.storage import get_storage

# A critical field below this confidence pulls the case into human review.
CRITICAL_FIELD_THRESHOLD = 0.85
# Any field below this is flagged for the reviewer's attention.
FIELD_REVIEW_THRESHOLD = 0.70


async def _emit(
    case_id: str,
    action: str,
    label: str,
    *,
    detail: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    model_version: str | None = None,
) -> None:
    """Write one line to the append-only event log.

    This is what the SSE stream replays, so it is also how the UI shows live progress. Its own
    session keeps it independent of whatever else the node is doing.
    """
    async with SessionLocal() as db:
        await record_event(
            db,
            case_id=UUID(case_id),
            action=action,
            label=label,
            actor="agent",
            actor_type=ActorType.agent,
            detail=detail,
            duration_ms=duration_ms,
            model_version=model_version,
        )
        await db.commit()


async def _load_doc_types() -> dict[str, models.DocumentType]:
    async with SessionLocal() as db:
        rows = (await db.execute(select(models.DocumentType))).scalars().all()
        return {row.key.value: row for row in rows}


# --------------------------------------------------------------------------- ocr


async def ocr_node(state: CaseState) -> dict[str, Any]:
    """Read the bytes of every document and pull out its text."""
    started = time.perf_counter()
    storage = get_storage()
    engine = get_ocr()
    updated: list[DocumentState] = []

    for document in state["documents"]:
        try:
            data = storage.read(document["storage_path"])
        except (OSError, ValueError):
            updated.append({**document, "ocr_text": "", "ocr_confidence": 0.0})
            continue
        result = engine.read(data, document["mime_type"])
        updated.append(
            {
                **document,
                "ocr_text": result.text,
                "ocr_confidence": result.confidence,
                "page_count": result.page_count,
            }
        )

    readable = sum(1 for d in updated if d["ocr_text"])
    await _emit(
        state["case_id"],
        "agent.ocr",
        f"Text read from {readable} of {len(updated)} document(s)",
        detail={"engine": engine.label, "readable": readable, "total": len(updated)},
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {"documents": updated}


# ---------------------------------------------------------------------- classify


async def classify_node(state: CaseState) -> dict[str, Any]:
    """Decide what each document is, and record the evidence for the decision."""
    started = time.perf_counter()
    updated: list[DocumentState] = []
    summary: dict[str, str] = {}

    for document in state["documents"]:
        doc_type, confidence, evidence = classify(document["ocr_text"], document["filename"])
        updated.append(
            {**document, "doc_type": doc_type.value, "classification_confidence": confidence}
        )
        summary[document["filename"]] = doc_type.value
        await _emit(
            state["case_id"],
            "agent.classify",
            f"{document['filename']} classified as {doc_type.value} ({confidence:.0%})",
            detail={"evidence": evidence, "confidence": confidence},
        )

    unknown = [d["filename"] for d in updated if d["doc_type"] == DocTypeKey.unknown.value]
    reasons: list[dict[str, str]] = []
    if unknown:
        reasons.append(
            {
                "code": "NEW_DOCUMENT_TYPE",
                "label": f"{len(unknown)} document(s) could not be classified",
            }
        )

    await _emit(
        state["case_id"],
        "agent.classify.done",
        f"Classified {len(updated)} document(s)",
        detail={"types": summary},
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {"documents": updated, "review_reasons": reasons}


# ----------------------------------------------------------------------- extract


async def extract_node(state: CaseState) -> dict[str, Any]:
    """Pull the schema's fields out of each document.

    The schema comes from the `document_types` table, so a new document type is configuration.
    M3 replaces this single pass with parallel workers and a critic.
    """
    started = time.perf_counter()
    doc_types = await _load_doc_types()
    extractor = get_extractor()
    fields: list[FieldState] = []
    order = 0

    for document in state["documents"]:
        definition = doc_types.get(document["doc_type"])
        if definition is None or not document["ocr_text"]:
            continue
        schema: list[dict[str, Any]] = list(definition.field_schema or [])
        lines = document["ocr_text"].split("\n")
        found = extractor.extract(lines, schema, document["doc_type"])

        for spec in schema:
            name = str(spec["name"])
            result = found.get(name)
            fields.append(
                {
                    "name": name,
                    "label_en": str(spec.get("label_en", name)),
                    "label_ar": str(spec.get("label_ar", "")),
                    "value": result.value if result else None,
                    # A field the schema wants but the document does not contain is a real
                    # signal, so it gets confidence 0 rather than being dropped.
                    "confidence": result.confidence if result else 0.0,
                    "is_critical": bool(spec.get("is_critical", False)),
                    "document_id": document["document_id"],
                    "page": result.page if result else None,
                    "bbox": None,
                    "source_text": result.source_text if result else None,
                    "order_index": order,
                }
            )
            order += 1

        await _emit(
            state["case_id"],
            "agent.extract",
            f"{len(found)} field(s) read from {document['filename']}",
            detail={"doc_type": document["doc_type"], "found": sorted(found)},
            model_version=extractor.model_version,
        )

    await _emit(
        state["case_id"],
        "agent.extract.done",
        f"{len(fields)} field(s) extracted across the case",
        detail={"extractor": extractor.label},
        duration_ms=int((time.perf_counter() - started) * 1000),
        model_version=extractor.model_version,
    )
    return {"fields": fields}


# ---------------------------------------------------------------------- validate


async def validate_node(state: CaseState) -> dict[str, Any]:
    """Run the document type's rules and work out whether a human is needed."""
    started = time.perf_counter()
    doc_types = await _load_doc_types()

    # Group the values by document type so cross-document rules can compare them.
    doc_type_by_id = {d["document_id"]: d["doc_type"] for d in state["documents"]}
    values_by_doc: dict[str, dict[str, str | None]] = {}
    for field in state["fields"]:
        doc_type = doc_type_by_id.get(field["document_id"] or "", "unknown")
        values_by_doc.setdefault(doc_type, {})[field["name"]] = field["value"]

    findings: list[FindingState] = []
    reasons: list[dict[str, str]] = []

    for doc_type, definition in doc_types.items():
        if doc_type not in values_by_doc:
            continue
        outcomes = rule_engine.evaluate(
            list(definition.rules or []), values_by_doc, doc_type, today=date.today()
        )
        for outcome in outcomes:
            if outcome.passed:
                continue
            findings.append(
                {
                    "code": outcome.rule_id,
                    "severity": outcome.severity,
                    "title": outcome.message,
                    "description": outcome.detail,
                    "policy_citation": outcome.policy,
                }
            )
            if outcome.severity == Severity.critical.value:
                reasons.append({"code": "DOCUMENT_EXPIRED", "label": outcome.message})
            elif outcome.rule_id.endswith("MATCHES_MOA"):
                reasons.append({"code": "CROSS_DOC_MISMATCH", "label": outcome.message})

    # Low confidence on a critical field is the other route into review.
    weak_critical = [
        f
        for f in state["fields"]
        if f["is_critical"] and f["confidence"] < CRITICAL_FIELD_THRESHOLD
    ]
    for weak in weak_critical:
        reasons.append(
            {
                "code": "LOW_CONFIDENCE_CRITICAL_FIELD",
                "label": f"{weak['label_en']} read with {weak['confidence']:.0%} confidence",
            }
        )

    scored = [f["confidence"] for f in state["fields"] if f["confidence"] > 0]
    confidence = round(sum(scored) / len(scored), 3) if scored else 0.0

    for finding in findings:
        await _emit(
            state["case_id"],
            "agent.finding",
            f"{finding['severity'].upper()}: {finding['title']}",
            detail={"code": finding["code"], "policy": finding["policy_citation"]},
        )

    await _emit(
        state["case_id"],
        "agent.validate",
        f"{len(findings)} finding(s); overall confidence {confidence:.0%}",
        detail={
            "confidence": confidence,
            "weak_critical_fields": [f["name"] for f in weak_critical],
        },
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {"findings": findings, "review_reasons": reasons, "confidence": confidence}


# ------------------------------------------------------------------- review gate


def needs_human(state: CaseState) -> str:
    """The conditional edge: does this case need a person?"""
    return "review_gate" if state.get("review_reasons") else "finalize"


async def review_gate_node(state: CaseState) -> dict[str, Any]:
    """Pause the graph and wait for a reviewer.

    NOTHING may be written before `interrupt()`. When the reviewer answers, LangGraph re-runs
    this node from the first line, so any write above the interrupt would happen twice. The
    review task row is created by the runner, outside the graph, exactly once.
    """
    decision = interrupt(
        {
            "case_id": state["case_id"],
            "reasons": state.get("review_reasons", []),
            "confidence": state.get("confidence", 0.0),
            "fields": [
                {
                    "name": f["name"],
                    "label_en": f["label_en"],
                    "value": f["value"],
                    "confidence": f["confidence"],
                    "is_critical": f["is_critical"],
                }
                for f in state["fields"]
                if f["is_critical"] or f["confidence"] < FIELD_REVIEW_THRESHOLD
            ],
        }
    )

    # --- everything below here runs only after a human answered ---
    corrections: dict[str, str] = dict(decision.get("corrections") or {})
    verdict = str(decision.get("decision", "approve"))

    # The corrections are returned as data, not applied to `fields` here: `fields` uses an
    # append reducer, so rewriting it would duplicate every row. The runner applies them when
    # it saves the case, in one place.
    await _emit(
        state["case_id"],
        "agent.review.resumed",
        f"Reviewer decision: {verdict}",
        detail={"corrections": sorted(corrections), "decision": verdict},
    )
    return {"decision": verdict, "corrections": corrections, "needs_review": False}


# ---------------------------------------------------------------------- finalize


async def finalize_node(state: CaseState) -> dict[str, Any]:
    """Close the case out. Posting to core banking is wired in M4."""
    decision = state.get("decision") or "auto"
    straight_through = decision == "auto"
    await _emit(
        state["case_id"],
        "agent.finalize",
        (
            "Completed without human review (straight-through)"
            if straight_through
            else f"Completed after review: {decision}"
        ),
        detail={"straight_through": straight_through, "decision": decision},
    )
    return {"straight_through": straight_through, "needs_review": False}
