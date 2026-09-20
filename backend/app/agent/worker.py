"""One extraction worker: read a document, validate, self-correct, score.

This is the body of the parallel worker node. One instance runs per document, so the loop here
concerns itself with exactly one document and knows nothing about the rest of the case.

**Self-correction (max two repairs).** The worker does not decide for itself whether its answer
looks right. It validates the answer against the Pydantic model built from the document type's
schema, and each validation error names a field and says what was wrong with it. A repair
strategy is chosen from that error — a date that did not parse is looked for again as a date
pattern, a number that did not parse is stripped of its currency — and the answer is validated
again. Two repairs, then the worker stops and hands the field to the reviewer with a low score
and a note saying what it tried.

Two is not arbitrary: each repair loosens the search, so a third would be guessing, and a loop
with no limit is the classic way an agent burns money on a document that simply does not
contain the field.

**Scoring.** The worker builds each field's confidence from signals (see `confidence.py`) and
records them, so the number on screen can be explained. The critic adds its own signal later.
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.agent import confidence as confidence_signals
from app.agent import schema as extraction_schema
from app.agent.extractor import ExtractedValue, get_extractor
from app.agent.state import FieldState
from app.rag import fewshot

# Hard limit on repair passes. Each one loosens the search; a third would be guessing.
MAX_REPAIRS = 2

_DATE_ANY = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b")
_NUMBER_ANY = re.compile(r"\b\d[\d,]*(\.\d+)?\b")
_INLINE = re.compile(r"^\s*(?P<label>[^:]{2,60}?)\s*[:\-]\s*(?P<value>.+?)\s*$")
_NORMALISE = re.compile(r"[^a-z0-9]+")


def _key(text: str) -> str:
    return _NORMALISE.sub(" ", text.lower()).strip()


def _label_keys(spec: dict[str, Any]) -> set[str]:
    name = str(spec["name"])
    keys = {_key(name), _key(name.replace("_", " "))}
    for label_key in ("label_en", "label_ar"):
        label = spec.get(label_key)
        if label:
            keys.add(_key(str(label)))
    return {key for key in keys if key}


class Repair:
    """One repair strategy: what it looks for, and how it explains itself."""

    def __init__(self, name: str, explanation: str) -> None:
        self.name = name
        self.explanation = explanation


REPAIRS = {
    "date_rescan": Repair(
        "date_rescan",
        "looked for a date anywhere on the lines around the label, in either accepted format",
    ),
    "number_clean": Repair(
        "number_clean",
        "removed a currency word and thousands separators, then re-read the number",
    ),
    "inline_label": Repair(
        "inline_label",
        "re-read the field as 'Label: value' on a single line instead of label-above-value",
    ),
    "drop": Repair(
        "drop",
        "no value on this page survived validation, so the field was left empty rather than "
        "filled with something that does not validate",
    ),
}


def _repair_date(lines: list[str], label_keys: set[str]) -> str | None:
    """Find a date on the lines that follow this field's own label.

    Deliberately **not** "anywhere in the document". A trade licence carries an issue date and
    an expiry date; a document-wide search for a date would happily put the issue date into
    the expiry field and call it a repair. A wrong value that validates is far more dangerous
    than an empty one, because nothing downstream can tell it is wrong.
    """
    for index, line in enumerate(lines):
        if _key(line) in label_keys:
            for candidate in lines[index : index + 4]:
                match = _DATE_ANY.search(candidate)
                if match:
                    return match.group(1)
    return None


def _repair_number(current: str | None, lines: list[str], label_keys: set[str]) -> str | None:
    if current:
        match = _NUMBER_ANY.search(current)
        if match:
            return match.group(0)
    for index, line in enumerate(lines):
        if _key(line) in label_keys:
            for candidate in lines[index : index + 3]:
                match = _NUMBER_ANY.search(candidate)
                if match:
                    return match.group(0)
    return None


def _repair_inline(lines: list[str], label_keys: set[str]) -> str | None:
    """Some documents write 'Expiry date: 2027-03-10' on one line. Read that shape too."""
    for line in lines:
        match = _INLINE.match(line)
        if match and _key(match.group("label")) in label_keys:
            value = match.group("value").strip()
            if value:
                return value
    return None


def _problems(
    model: Any, values: dict[str, str | None], field_schema: list[dict[str, Any]]
) -> tuple[bool, list[extraction_schema.FieldError]]:
    """Everything worth repairing: schema violations, plus required fields that came back empty.

    The Pydantic model makes every field optional on purpose — a document that does not
    contain a value must produce `None`, not an invention. But a *required* field coming back
    empty is still something to have another go at, because the usual cause is a layout the
    label reader did not recognise, not a document that is genuinely missing it.
    """
    valid, errors = extraction_schema.validate(model, values)
    named = {error.field for error in errors}
    missing = [
        extraction_schema.FieldError(
            field=name,
            kind="missing",
            message="required field came back empty",
        )
        for name in extraction_schema.required_fields(field_schema)
        if name not in named and not (values.get(name) or "").strip()
    ]
    return (valid and not missing), [*errors, *missing]


def _strategies_for(error_kind: str, expected: str) -> list[str]:
    """Which repairs are worth trying for this kind of failure, in order.

    An empty field is most often a layout the label reader did not recognise, so the inline
    form is tried first. A malformed value is most often the right line read badly, so the
    shape-specific repair is tried first. Each strategy is tried at most once per field, and
    when the list runs out the field is dropped rather than guessed at.
    """
    shape = {"date": "date_rescan", "number": "number_clean"}.get(expected)
    if error_kind == "missing":
        return ["inline_label", *( [shape] if shape else [] )]
    return [*([shape] if shape else []), "inline_label"]


def _repair(
    *,
    error: extraction_schema.FieldError,
    expected: str,
    current: str | None,
    lines: list[str],
    label_keys: set[str],
    tried: set[str],
) -> tuple[str | None, str]:
    """Run the next untried repair for this field, or drop it."""
    for strategy in _strategies_for(error.kind, expected):
        if strategy in tried:
            continue
        tried.add(strategy)
        if strategy == "date_rescan":
            repaired = _repair_date(lines, label_keys)
        elif strategy == "number_clean":
            repaired = _repair_number(current, lines, label_keys)
        else:
            repaired = _repair_inline(lines, label_keys)
        if repaired:
            return repaired, strategy
        # A strategy that found nothing is still recorded: "we looked there and it was not
        # there" is part of the explanation a reviewer gets.
        return None, strategy
    return None, "drop"


def extract_document(
    document: dict[str, Any],
    field_schema: list[dict[str, Any]],
    *,
    order_offset: int = 0,
) -> tuple[list[FieldState], dict[str, Any]]:
    """Extract every field of one document, repairing what does not validate.

    Returns the fields and a report: attempts used, repairs applied, examples selected.
    """
    started = time.perf_counter()
    extractor = get_extractor()
    doc_type = str(document["doc_type"])
    # The guardrails node put a cleaned copy of the text in `safe_text`; the raw text is only
    # a fallback for a state that predates it.
    text = str(document.get("safe_text") or document.get("ocr_text") or "")
    lines = text.split("\n")

    found = extractor.extract(lines, field_schema, doc_type)
    values: dict[str, str | None] = {}
    for spec in field_schema:
        name = str(spec["name"])
        result = found.get(name)
        values[name] = result.value if result else None

    model = extraction_schema.build_model(doc_type, field_schema)
    repairs: list[dict[str, str]] = []
    attempts_by_field: dict[str, int] = dict.fromkeys(values, 1)
    types = extraction_schema.expected_types(field_schema)
    specs = {str(spec["name"]): spec for spec in field_schema}

    ok, errors = _problems(model, values, field_schema)
    passes = 0
    tried: dict[str, set[str]] = {}
    while not ok and passes < MAX_REPAIRS:
        passes += 1

        for error in errors:
            name = error.field
            spec = specs.get(name)
            if spec is None:
                values.pop(name, None)
                continue
            label_keys = _label_keys(spec)
            attempts_by_field[name] = attempts_by_field.get(name, 1) + 1

            repaired, strategy = _repair(
                error=error,
                expected=types.get(name, "string"),
                current=values.get(name),
                lines=lines,
                label_keys=label_keys,
                tried=tried.setdefault(name, set()),
            )
            repairs.append(
                {
                    "field": name,
                    "pass": str(passes),
                    "strategy": strategy,
                    "error": error.message,
                    "explanation": REPAIRS[strategy].explanation,
                    "before": values.get(name) or "",
                    "after": repaired or "",
                }
            )
            # A repair that found nothing leaves the field empty rather than keeping a value
            # that does not validate.
            values[name] = repaired

        ok, errors = _problems(model, values, field_schema)

    # Whatever is still invalid after the last pass is emptied. A missing required field is
    # not emptied again — it is already empty, and that is a finding for the rules, not a
    # failure of the extractor.
    valid, pydantic_errors = extraction_schema.validate(model, values)
    if not valid:
        for error in pydantic_errors:
            values[error.field] = None
            repairs.append(
                {
                    "field": error.field,
                    "pass": str(passes + 1),
                    "strategy": "drop",
                    "error": error.message,
                    "explanation": REPAIRS["drop"].explanation,
                    "before": "",
                    "after": "",
                }
            )
    # A field we tried to repair and still could not fill is recorded as given up on, so the
    # reviewer sees "we looked, twice, and it is not there" rather than an unexplained blank.
    for name, attempted in tried.items():
        if (values.get(name) or "").strip():
            continue
        if any(r["field"] == name and r["strategy"] == "drop" for r in repairs):
            continue
        repairs.append(
            {
                "field": name,
                "pass": str(passes + 1),
                "strategy": "drop",
                "error": "no repair produced a value that validates",
                "explanation": REPAIRS["drop"].explanation,
                "before": "",
                "after": "",
                "tried": ", ".join(sorted(attempted)),
            }
        )

    valid, _ = extraction_schema.validate(model, values)

    examples = [selection.as_dict() for selection in fewshot.select(doc_type, text, k=2)]
    fields = _to_fields(
        document=document,
        field_schema=field_schema,
        values=values,
        found=found,
        attempts=attempts_by_field,
        order_offset=order_offset,
    )

    report = {
        "document_id": str(document["document_id"]),
        "filename": str(document["filename"]),
        "doc_type": doc_type,
        "field_count": len(fields),
        "attempts": 1 + passes,
        "repairs": repairs,
        "examples": examples,
        "validated": valid,
        "prompt_version": "",
        "model_version": extractor.model_version,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    return fields, report


def _to_fields(
    *,
    document: dict[str, Any],
    field_schema: list[dict[str, Any]],
    values: dict[str, str | None],
    found: dict[str, ExtractedValue],
    attempts: dict[str, int],
    order_offset: int,
) -> list[FieldState]:
    """Turn validated values into field states, scoring each one from its signals."""
    text = str(document.get("safe_text") or document.get("ocr_text") or "")
    ocr_confidence = float(document.get("ocr_confidence") or 0.0)
    types = extraction_schema.expected_types(field_schema)

    fields: list[FieldState] = []
    for order, spec in enumerate(field_schema):
        name = str(spec["name"])
        value = values.get(name)
        original = found.get(name)

        signals = [
            confidence_signals.ocr_signal(ocr_confidence),
            confidence_signals.grounding(value, text),
            confidence_signals.label_signal(
                matched_label=original is not None,
                source_text=original.source_text if original else None,
            ),
            confidence_signals.shape(value, types.get(name, "string")),
        ]
        breakdown = confidence_signals.combine(
            signals, self_corrections=max(0, attempts.get(name, 1) - 1)
        )

        fields.append(
            {
                "name": name,
                "label_en": str(spec.get("label_en", name)),
                "label_ar": str(spec.get("label_ar", "")),
                "value": value,
                "confidence": breakdown.raw,
                "calibrated_confidence": breakdown.raw,
                "signals": breakdown.as_dict()["signals"],
                "is_critical": bool(spec.get("is_critical", False)),
                "document_id": str(document["document_id"]),
                "page": original.page if original else None,
                "bbox": None,
                "source_text": original.source_text if original else None,
                "attempts": attempts.get(name, 1),
                "critic": None,
                "order_index": order_offset + order,
            }
        )
    return fields
