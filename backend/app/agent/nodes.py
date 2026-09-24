"""The graph nodes: one small, explainable step each.

Every node takes the state, does one job, and returns only the keys it changed. LangGraph
merges those keys into the state and checkpoints the result, so the case can stop and resume
between any two nodes.

The order, and why each step is where it is:

    ocr          read the bytes; nothing else can happen first
    guardrails   inspect the text BEFORE anything reads it as instructions
    supervisor   classify each document and fan out one worker per document (Send API)
    extract      the workers, in parallel, each self-correcting on its own validation errors
    critic       challenge the values a second way (actor-critic)
    investigator answer what the documents cannot answer, with MCP tools (ReAct)
    validate     versioned rules, policy citations, calibrated confidence
    review_gate  interrupt() when a person must decide
    finalize     close the case out

The review gate is the one node with a hard rule: **it must not change anything before it
calls `interrupt()`**, because when a reviewer answers, LangGraph re-runs the node from the
top. Anything written before the interrupt would be written twice.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any
from uuid import UUID

from langgraph.types import Send, interrupt
from sqlalchemy import select

from app.agent import calibration, rulepacks
from app.agent import confidence as confidence_signals
from app.agent import critic as critic_module
from app.agent import investigator as investigator_module
from app.agent import rules as rule_engine
from app.agent.classifier import classify
from app.agent.extractor import get_extractor
from app.agent.ocr import get_ocr
from app.agent.state import CaseState, DocumentState, FieldState, FindingState, WorkerInput
from app.agent.tools import ToolBroker
from app.agent.translate import get_translator, translate_values
from app.agent.worker import extract_document
from app.casetypes import profile_for
from app.db import models
from app.db.enums import ActorType, DocTypeKey, Severity
from app.db.session import SessionLocal
from app.guardrails import screen_async
from app.rag import index as policy_index
from app.services.events import record_event
from app.services.storage import get_storage

# A critical field below this calibrated confidence pulls the case into human review.
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
    prompt_version: str | None = None,
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
            prompt_version=prompt_version,
        )
        await db.commit()


async def _load_doc_types() -> dict[str, models.DocumentType]:
    async with SessionLocal() as db:
        rows = (await db.execute(select(models.DocumentType))).scalars().all()
        return {row.key.value: row for row in rows}


async def _load_prompt_bodies(pins: dict[str, str]) -> dict[str, str]:
    """The text of each pinned prompt version, keyed by `"<key>@<version>"`.

    Read here, in the supervisor, so the extraction workers stay free of database access —
    they run in parallel and a model-backed one would otherwise open a connection each.

    The pin is the exact version recorded on the document type, never "the newest" and never
    "the approved one". A case must be explainable after the fact, and that requires the
    wording that actually ran, which is why the version is stored on the case. (M6)
    """
    if not pins:
        return {}
    wanted = {value for value in pins.values() if value and "@" in value}
    if not wanted:
        return {}

    bodies: dict[str, str] = {}
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(models.Prompt.key, models.PromptVersion.version, models.PromptVersion.body)
                .join(models.PromptVersion, models.PromptVersion.prompt_id == models.Prompt.id)
            )
        ).all()
    for key, version, body in rows:
        pin = f"{key}@{version}"
        if pin in wanted:
            bodies[pin] = body or ""
    return bodies


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
                # Empty unless the engine reports geometry. Checkpointed with the rest of the
                # state, so a resumed case keeps its highlight boxes.
                "line_boxes": [box.as_dict() for box in result.line_boxes],
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


# -------------------------------------------------------------------- guardrails


async def guardrails_node(state: CaseState) -> dict[str, Any]:
    """Inspect every document before anything treats its text as meaningful.

    Three checks run here — prompt shield, content safety, PII tokenisation — and the cleaned
    text is put on the document as `safe_text`. From this point on, the pipeline works from
    `safe_text`; the original stays on the record for the reviewer to look at.

    Nothing is rejected. A document that trips a guardrail goes to a person, because the
    common cause is a bad scan and the rare cause is an attack, and both need a human.
    """
    started = time.perf_counter()
    updated: list[DocumentState] = []
    reports: list[dict[str, Any]] = []
    reasons: list[dict[str, str]] = []
    findings: list[FindingState] = []

    for document in state["documents"]:
        # `screen_async` so Azure Prompt Shields and Content Safety can be asked as well when
        # they are configured. With no endpoint set it is exactly the local `screen()`.
        report, _vault = await screen_async(
            document["document_id"], document["filename"], document.get("ocr_text", "")
        )
        # `clean_text`, not `log_text`: the pipeline must read the real values. The vault
        # (token → real value) and the tokenised copy stay in this function and are never
        # checkpointed — tokenisation protects logs, not the pipeline.
        updated.append({**document, "safe_text": report.clean_text})
        reports.append(report.as_dict())

        if report.injection.get("attacked"):
            kinds = sorted({s["kind"] for s in report.injection.get("signals", [])})
            findings.append(
                {
                    "code": "SUSPECTED_INJECTION",
                    "severity": Severity.critical.value,
                    "title": f"Hidden instructions found in {document['filename']}",
                    "description": (
                        "The document contains text shaped like an instruction "
                        f"({', '.join(kinds)}). It was never acted on: document text is data, "
                        "never a command. The case is referred to a person."
                    ),
                    "policy_citation": "AI-POL-001 §2.1",
                    "source": "guardrails",
                }
            )
            reasons.append(
                {
                    "code": "SUSPECTED_INJECTION",
                    "label": f"{document['filename']} may contain hidden instructions",
                }
            )

        if report.safety.get("flagged"):
            findings.append(
                {
                    "code": "UNSAFE_CONTENT",
                    "severity": Severity.critical.value,
                    "title": f"Content safety flagged {document['filename']}",
                    "description": (
                        "The upload was flagged by the content-safety check "
                        f"({', '.join(report.safety.get('matches', []))}). A person must look "
                        "at it before the case continues."
                    ),
                    "policy_citation": "AI-POL-001 §3.1",
                    "source": "guardrails",
                }
            )
            reasons.append(
                {"code": "UNSAFE_CONTENT", "label": f"{document['filename']} flagged as unsafe"}
            )

        await _emit(
            state["case_id"],
            "agent.guardrails.document",
            (
                f"{document['filename']}: {len(report.pii_counts)} PII type(s) tokenised for "
                "logs; "
                + (
                    "injection patterns found"
                    if report.injection.get("attacked")
                    else "no injection patterns"
                )
            ),
            detail=report.as_dict(),
        )

    blocked = sum(1 for report in reports if report.get("blocked"))
    await _emit(
        state["case_id"],
        "agent.guardrails",
        (
            f"Guardrails cleared {len(reports) - blocked} of {len(reports)} document(s)"
            if reports
            else "No documents to screen"
        ),
        detail={
            "documents": len(reports),
            "blocked": blocked,
            "checks": ["prompt shield", "content safety", "PII tokenisation"],
        },
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "documents": updated,
        "guardrails": reports,
        "findings": await cite_findings(findings),
        "review_reasons": reasons,
    }


# -------------------------------------------------------------------- supervisor


async def supervisor_node(state: CaseState) -> dict[str, Any]:
    """Classify each document and decide who reads what.

    This is the supervisor half of supervisor-worker. It does no extraction itself: it works
    out what each document is, picks the schema and the prompt version for it, and writes a
    plan. `fan_out` then turns that plan into one `Send` per document, and the workers run in
    parallel.
    """
    started = time.perf_counter()
    doc_types = await _load_doc_types()
    updated: list[DocumentState] = []
    plan: list[dict[str, Any]] = []
    reasons: list[dict[str, str]] = []
    prompt_versions: dict[str, str] = {}

    for index, document in enumerate(state["documents"]):
        text = document.get("safe_text") or document.get("ocr_text", "")
        doc_type, confidence, evidence = classify(text, document["filename"])
        updated.append(
            {**document, "doc_type": doc_type.value, "classification_confidence": confidence}
        )

        definition = doc_types.get(doc_type.value)
        schema = list(definition.field_schema or []) if definition else []
        prompt_key = definition.prompt_key if definition else ""
        if definition:
            prompt_versions[doc_type.value] = f"{prompt_key}@{definition.version}"

        plan.append(
            {
                "document_id": document["document_id"],
                "filename": document["filename"],
                "doc_type": doc_type.value,
                "classification_confidence": confidence,
                "evidence": evidence,
                "field_count": len(schema),
                "field_schema": schema,
                "worker": "extract_worker",
                # A document with no schema has no worker to send it to, and saying so here is
                # what stops the fan-out from starting a worker with nothing to do.
                "dispatched": bool(schema) and bool(text),
                "skipped_because": (
                    "" if schema and text else
                    "no text could be read" if not text else
                    "no schema is configured for this document type"
                ),
                "order_offset": index * 100,
                "prompt_version": prompt_versions.get(doc_type.value, ""),
            }
        )

        await _emit(
            state["case_id"],
            "agent.classify",
            f"{document['filename']} classified as {doc_type.value} ({confidence:.0%})",
            detail={"evidence": evidence, "confidence": confidence},
        )

    # The wording each worker will actually send (M6). One query for the whole case, before
    # the fan-out, rather than one per worker. Empty bodies in demo mode are harmless: the
    # deterministic extractor ignores the prompt entirely.
    prompt_bodies = await _load_prompt_bodies(prompt_versions)
    for item in plan:
        item["prompt_body"] = prompt_bodies.get(str(item.get("prompt_version", "")), "")

    unknown = [d["filename"] for d in updated if d["doc_type"] == DocTypeKey.unknown.value]
    if unknown:
        reasons.append(
            {
                "code": "NEW_DOCUMENT_TYPE",
                "label": f"{len(unknown)} document(s) could not be classified",
            }
        )

    dispatched = sum(1 for item in plan if item["dispatched"])
    await _emit(
        state["case_id"],
        "agent.supervisor",
        f"Supervisor dispatched {dispatched} worker(s) in parallel",
        # The plan is summarised for the timeline: the prompt bodies would bloat every event
        # row, and the version pin is the thing an auditor needs.
        detail={
            "plan": [
                {key: value for key, value in item.items() if key != "prompt_body"}
                for item in plan
            ],
            "prompt_versions": prompt_versions,
        },
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "documents": updated,
        "plan": plan,
        "review_reasons": reasons,
        "prompt_versions": prompt_versions,
    }


def fan_out(state: CaseState) -> list[Send] | str:
    """The Send API: one worker per document, all in the same superstep.

    Returning a list of `Send` objects is what makes the workers run in parallel rather than
    one after another. Each `Send` carries only that worker's slice of the problem.

    A case whose documents were all skipped has nothing to fan out to, and goes straight to
    the critic, which will have nothing to challenge and will say so.
    """
    sends: list[Send] = []
    documents = {document["document_id"]: document for document in state["documents"]}

    for item in state.get("plan", []):
        if not item.get("dispatched"):
            continue
        document = documents.get(item["document_id"])
        if document is None:
            continue
        payload: WorkerInput = {
            "case_id": state["case_id"],
            "document": document,
            "field_schema": item.get("field_schema") or [],
            "order_offset": int(item.get("order_offset", 0)),
            "prompt_version": str(item.get("prompt_version", "")),
            "prompt_body": str(item.get("prompt_body", "")),
        }
        sends.append(Send("extract_worker", payload))

    return sends or "critic"


# ------------------------------------------------------------------ extract work


async def extract_worker_node(payload: WorkerInput) -> dict[str, Any]:
    """One worker, one document. Runs in parallel with the other workers.

    It gets its own slice of the problem — a document and a schema — and knows nothing about
    the rest of the case, which is what makes running several of them at once safe.
    """
    document = payload["document"]
    case_id = payload["case_id"]
    fields, report = extract_document(
        document,
        payload["field_schema"],
        order_offset=payload["order_offset"],
        prompt_body=payload.get("prompt_body", ""),
    )
    report["prompt_version"] = payload.get("prompt_version", "")

    repairs = report["repairs"]
    await _emit(
        case_id,
        "agent.extract",
        (
            f"{document['filename']}: {len(fields)} field(s) read"
            + (f", {len(repairs)} self-correction(s)" if repairs else "")
        ),
        detail={
            "doc_type": document["doc_type"],
            "attempts": report["attempts"],
            "repairs": repairs,
            "examples_selected": report["examples"],
            "validated": report["validated"],
        },
        duration_ms=report["duration_ms"],
        model_version=report["model_version"],
        prompt_version=report["prompt_version"] or None,
    )
    return {"fields": fields, "worker_results": [report]}


# ------------------------------------------------------------------------ critic


async def critic_node(state: CaseState) -> dict[str, Any]:
    """Challenge the extracted values a second, different way (actor-critic)."""
    started = time.perf_counter()
    doc_types = await _load_doc_types()
    documents = {document["document_id"]: document for document in state["documents"]}
    broker = ToolBroker.for_node("critic")

    notes: list[dict[str, Any]] = []
    revised: list[FieldState] = []
    reasons: list[dict[str, str]] = []
    disagreements = 0

    for field in state.get("fields", []):
        document = documents.get(str(field.get("document_id") or ""))
        if document is None:
            continue
        definition = doc_types.get(document["doc_type"])
        schema = list(definition.field_schema or []) if definition else []
        expected = {
            str(spec["name"]): str(spec.get("type", "string")) for spec in schema
        }.get(field["name"], "string")

        verdict = await critic_module.review_field(
            field,
            document=document,
            expected_type=expected,
            label_keys=critic_module.label_index(schema),
            broker=broker,
        )
        notes.append(verdict.as_dict())

        # The critic's verdict is the fifth confidence signal, so the field is re-scored.
        signals = confidence_signals.from_dicts(list(field.get("signals") or []))
        signals = [signal for signal in signals if signal.key != "critic"]
        critic_signal = confidence_signals.critic_signal(verdict.agreed, verdict.reason)
        if critic_signal is not None:
            signals.append(critic_signal)
        breakdown = confidence_signals.combine(
            signals, self_corrections=max(0, int(field.get("attempts", 1)) - 1)
        )

        revised.append(
            {
                **field,
                "confidence": breakdown.raw,
                "calibrated_confidence": breakdown.raw,
                "signals": breakdown.as_dict()["signals"],
                "critic": verdict.as_dict(),
            }
        )

        if not verdict.agreed:
            disagreements += 1
            if field.get("is_critical"):
                reasons.append(
                    {
                        "code": "CRITIC_DISAGREEMENT",
                        "label": f"{field['label_en']}: {verdict.reason}",
                    }
                )

    await _emit(
        state["case_id"],
        "agent.critic",
        (
            f"Critic checked {len(notes)} field(s); {disagreements} disagreement(s)"
            if notes
            else "Critic had no fields to check"
        ),
        detail={
            "checked": len(notes),
            "disagreements": disagreements,
            "via": sorted({note["via"] for note in notes}) if notes else [],
        },
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "fields": revised,
        "critic_notes": notes,
        "review_reasons": reasons,
        "tool_calls": broker.record(),
    }


# ------------------------------------------------------------------ investigator


def _values_by_doc(state: CaseState) -> dict[str, dict[str, str | None]]:
    doc_type_by_id = {d["document_id"]: d["doc_type"] for d in state["documents"]}
    values: dict[str, dict[str, str | None]] = {}
    for field in state.get("fields", []):
        doc_type = doc_type_by_id.get(str(field.get("document_id") or ""), "unknown")
        values.setdefault(doc_type, {})[field["name"]] = field["value"]
    return values


async def investigator_node(state: CaseState) -> dict[str, Any]:
    """Answer what the documents cannot answer, using MCP tools, in a bounded ReAct loop."""
    started = time.perf_counter()
    broker = ToolBroker.for_node("investigator")
    questions = investigator_module.plan(
        _values_by_doc(state), profile_for(state["case_type"])
    )
    outcome = await investigator_module.investigate(questions, broker)

    for step in outcome.steps:
        await _emit(
            state["case_id"],
            "agent.investigate.step",
            f"Step {step.index}: {step.action} → {step.observation}",
            detail=step.as_dict(),
            duration_ms=step.duration_ms,
        )

    findings: list[FindingState] = [
        {
            "code": str(item["code"]),
            "severity": str(item["severity"]),
            "title": str(item["title"]),
            "description": str(item["description"]),
            "policy_citation": item.get("policy_citation"),
            "source": "investigator",
        }
        for item in outcome.findings
    ]

    await _emit(
        state["case_id"],
        "agent.investigate",
        (
            f"Investigator ran {len(outcome.steps)} step(s) and reached "
            f"{len(outcome.findings)} conclusion(s)"
            if outcome.steps
            else "Nothing to investigate"
        ),
        detail={
            "controller": outcome.controller,
            "questions": [question.prompt for question in questions],
            "step_limit": investigator_module.MAX_STEPS,
            "tool_calls": broker.succeeded,
        },
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "investigation": [step.as_dict() for step in outcome.steps],
        "findings": await cite_findings(findings),
        "review_reasons": outcome.review_reasons,
        "tool_calls": broker.record(),
    }


# ---------------------------------------------------------------------- validate


async def validate_node(state: CaseState) -> dict[str, Any]:
    """Run the versioned rules, cite the policy behind each finding, calibrate confidence."""
    started = time.perf_counter()
    doc_types = await _load_doc_types()
    values_by_doc = _values_by_doc(state)

    findings: list[FindingState] = []
    reasons: list[dict[str, str]] = []
    packs_used: dict[str, str] = {}
    not_evaluated: list[str] = []

    for doc_type in values_by_doc:
        pack = rulepacks.pack_for(doc_type)
        if pack is not None:
            rules, pack_id, pack_version = pack.rules, pack.id, pack.version
        else:
            # No YAML pack covers this type, so the editable rows on the document type run
            # instead — and the case records which source judged it.
            definition = doc_types.get(doc_type)
            if definition is None:
                continue
            rules = list(definition.rules or [])
            pack_id, pack_version = "document_types table", definition.rules_version
        packs_used[doc_type] = f"{pack_id}@{pack_version}"

        outcomes = rule_engine.evaluate(
            rules,
            values_by_doc,
            doc_type,
            today=date.today(),
            pack_id=pack_id,
            pack_version=pack_version,
        )
        for outcome in outcomes:
            if not outcome.evaluated:
                not_evaluated.append(outcome.rule_id)
                continue
            if outcome.passed:
                continue
            findings.append(
                {
                    "code": outcome.rule_id,
                    "severity": outcome.severity,
                    "title": outcome.message,
                    "description": (
                        f"{outcome.detail}. {outcome.explain}".strip()
                        if outcome.explain
                        else outcome.detail
                    ),
                    "policy_citation": outcome.policy,
                    "source": f"rules:{packs_used[doc_type]}",
                }
            )
            if outcome.severity == Severity.critical.value:
                reasons.append({"code": "DOCUMENT_EXPIRED", "label": outcome.message})
            elif outcome.rule_id.endswith("MATCHES_MOA") or outcome.rule_id.endswith(
                "MATCHES_PASSPORT"
            ):
                reasons.append({"code": "CROSS_DOC_MISMATCH", "label": outcome.message})

    # --- reading aid: the English of an Arabic value, beside it and never over it ---
    # One call for the whole case, and only for values that actually contain Arabic. A failure
    # here costs a convenience, not a case: `translate_values` returns "no translation".
    fields_in = list(state.get("fields", []))
    translations = translate_values([field.get("value") for field in fields_in])
    translated_count = sum(1 for item in translations if item.text)
    fields_in = [
        {**field, "value_translated": item.text, "translation_source": item.source}
        for field, item in zip(fields_in, translations, strict=False)
    ]
    if translated_count:
        await _emit(
            state["case_id"],
            "agent.translate",
            f"{translated_count} value(s) shown in English beside the original",
            detail={
                "translated": translated_count,
                "source": get_translator().name,
                "note": "A translation is a reading aid; the stored value is the document's.",
            },
        )

    # --- calibration: raw score in, calibrated probability out ---
    curve = calibration.active()
    calibrated_fields: list[FieldState] = [
        {**field, "calibrated_confidence": curve.apply(float(field.get("confidence", 0.0)))}
        for field in fields_in
    ]

    # Low confidence on a critical field is the other route into review. The *calibrated*
    # number is what the threshold reads, because that is the one that means what it says.
    weak_critical = [
        field
        for field in calibrated_fields
        if field["is_critical"]
        and float(field.get("calibrated_confidence", 0.0)) < CRITICAL_FIELD_THRESHOLD
    ]
    for weak in weak_critical:
        reasons.append(
            {
                "code": "LOW_CONFIDENCE_CRITICAL_FIELD",
                "label": (
                    f"{weak['label_en']} read with "
                    f"{float(weak.get('calibrated_confidence', 0.0)):.0%} confidence"
                ),
            }
        )

    # The case's confidence averages the fields that actually carry a value. A field the
    # document simply does not contain is a completeness question — the "is present" rules
    # answer it — and counting its low score here would make a perfectly read document look
    # doubtful because its schema has optional fields.
    scored = [
        float(field.get("calibrated_confidence", 0.0))
        for field in calibrated_fields
        if field.get("value")
    ]
    confidence = round(sum(scored) / len(scored), 3) if scored else 0.0

    # --- policy citations, retrieved rather than hard-coded ---
    # Only this node's own findings: `findings` has an append reducer, so the ones the
    # guardrails and the investigator produced are already in the state, already cited.
    new_findings = await cite_findings(findings)

    for finding in new_findings:
        await _emit(
            state["case_id"],
            "agent.finding",
            f"{finding['severity'].upper()}: {finding['title']}",
            detail={
                "code": finding["code"],
                "policy": finding.get("policy_citation"),
                "quote": finding.get("policy_quote"),
                "source": finding.get("source"),
            },
        )

    await _emit(
        state["case_id"],
        "agent.validate",
        f"{len(new_findings)} finding(s); overall confidence {confidence:.0%}",
        detail={
            "confidence": confidence,
            "calibrated": curve.fitted,
            "rule_packs": packs_used,
            "rules_not_evaluated": not_evaluated,
            "weak_critical_fields": [field["name"] for field in weak_critical],
        },
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "fields": calibrated_fields,
        "findings": new_findings,
        "review_reasons": reasons,
        "confidence": confidence,
        "rule_packs": packs_used,
        "calibration": curve.as_dict(),
    }


async def cite_findings(findings: list[FindingState]) -> list[FindingState]:
    """Attach the policy text behind each finding, retrieved from the index.

    Most findings already name their section, so this is a look-up. The rest get the nearest
    section by vector search, and anything with no good match gets no quote at all rather than
    a misleading one.
    """
    cited: list[FindingState] = []
    async with SessionLocal() as db:
        for finding in findings:
            quote = finding.get("policy_quote")
            if not quote:
                retrieved = await policy_index.cite(
                    db,
                    finding.get("policy_citation"),
                    f"{finding['title']} {finding['description']}",
                )
                if retrieved is not None:
                    finding = {
                        **finding,
                        "policy_citation": finding.get("policy_citation") or retrieved.citation,
                        "policy_quote": retrieved.quote,
                    }
            cited.append(finding)
    return cited


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
                    "confidence": float(f.get("calibrated_confidence", f["confidence"])),
                    "is_critical": f["is_critical"],
                    "critic": f.get("critic"),
                }
                for f in state["fields"]
                if f["is_critical"]
                or float(f.get("calibrated_confidence", f["confidence"])) < FIELD_REVIEW_THRESHOLD
                or (f.get("critic") or {}).get("agreed") is False
            ],
        }
    )

    # --- everything below here runs only after a human answered ---
    corrections: dict[str, str] = dict(decision.get("corrections") or {})
    verdict = str(decision.get("decision", "approve"))

    # The corrections are returned as data, not applied to `fields` here: the runner applies
    # them when it saves the case, in one place.
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
    extractor = get_extractor()
    await _emit(
        state["case_id"],
        "agent.finalize",
        (
            "Completed without human review (straight-through)"
            if straight_through
            else f"Completed after review: {decision}"
        ),
        detail={
            "straight_through": straight_through,
            "decision": decision,
            "tool_calls": len(state.get("tool_calls", [])),
            "rule_packs": state.get("rule_packs", {}),
        },
        model_version=extractor.model_version,
    )
    return {"straight_through": straight_through, "needs_review": False}
