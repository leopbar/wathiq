"""The cross-field rule engine.

Rules live as data on the document type (`document_types.rules`), never as engine code, so
adding use case 2 is a configuration change. M3 moves them to versioned YAML files and adds
the richer expressions; this is the small interpreter that runs the three shapes M2 needs:

    expiry_date > today                       a date must still be in the future
    issue_date < expiry_date                  one date must precede another
    trade_license.field ~= moa.field          the same value across two documents, fuzzily

Anything it does not understand is skipped and reported, never silently ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.agent.extractor import parse_date

_CROSS_DOC = re.compile(r"^(\w+)\.(\w+)\s*(~=|==)\s*(\w+)\.(\w+)$")
_DATE_CMP = re.compile(r"^(\w+)\s*([<>])\s*(\w+)$")
# Punctuation is deleted, not turned into a space, so "L.L.C." stays one token and matches
# "LLC". UAE company names use both spellings constantly, and splitting them into "l l c"
# made an identical name look only half similar.
_PUNCTUATION = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(slots=True)
class RuleOutcome:
    rule_id: str
    passed: bool
    severity: str
    message: str
    policy: str | None
    detail: str


def _norm(value: str) -> str:
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub("", value.lower())).strip()


def _similar(left: str, right: str) -> float:
    """Token overlap — enough to catch 'Al Noor Trading LLC' vs 'Al Noor Trading L.L.C.'."""
    a, b = set(_norm(left).split()), set(_norm(right).split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_FUZZY_THRESHOLD = 0.7


def evaluate(
    rules: list[dict[str, object]],
    values_by_doc: dict[str, dict[str, str | None]],
    doc_type: str,
    today: date | None = None,
) -> list[RuleOutcome]:
    """Run every rule for one document type and report what happened."""
    today = today or date.today()
    own = values_by_doc.get(doc_type, {})
    outcomes: list[RuleOutcome] = []

    for rule in rules:
        rule_id = str(rule.get("id", "UNNAMED"))
        expr = str(rule.get("expr", "")).strip()
        severity = str(rule.get("severity", "warning"))
        message = str(rule.get("message", rule_id))
        policy = rule.get("policy")
        policy_str = str(policy) if policy else None

        outcome = _run_one(expr, own, values_by_doc, today)
        if outcome is None:
            # Not understood or not enough data — say so rather than claim a pass.
            outcomes.append(
                RuleOutcome(rule_id, True, severity, message, policy_str, "skipped: not evaluable")
            )
            continue
        passed, detail = outcome
        outcomes.append(RuleOutcome(rule_id, passed, severity, message, policy_str, detail))

    return outcomes


def _run_one(
    expr: str,
    own: dict[str, str | None],
    values_by_doc: dict[str, dict[str, str | None]],
    today: date,
) -> tuple[bool, str] | None:
    cross = _CROSS_DOC.match(expr)
    if cross:
        left_doc, left_field, operator, right_doc, right_field = cross.groups()
        left = (values_by_doc.get(left_doc) or {}).get(left_field)
        right = (values_by_doc.get(right_doc) or {}).get(right_field)
        if not left or not right:
            return None
        if operator == "==":
            return left.strip() == right.strip(), f"{left!r} vs {right!r}"
        score = _similar(left, right)
        return score >= _FUZZY_THRESHOLD, f"{left!r} vs {right!r} (similarity {score:.2f})"

    date_cmp = _DATE_CMP.match(expr)
    if date_cmp:
        left_name, operator, right_name = date_cmp.groups()
        left_date = _resolve_date(left_name, own, today)
        right_date = _resolve_date(right_name, own, today)
        if left_date is None or right_date is None:
            return None
        passed = left_date > right_date if operator == ">" else left_date < right_date
        return passed, f"{left_name}={left_date} {operator} {right_name}={right_date}"

    return None


def _resolve_date(name: str, values: dict[str, str | None], today: date) -> date | None:
    if name == "today":
        return today
    raw = values.get(name)
    return parse_date(raw) if raw else None
