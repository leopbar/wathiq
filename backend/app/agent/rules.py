"""The cross-field rule engine.

Rules are **data**, never engine code: they live in versioned YAML rule packs
(`app/agent/rulepacks/*.yaml`), so adding use case 2 — or changing a bank policy — is a
configuration change with a version number and a diff, not a deployment of new logic.

The engine understands six shapes. Everything a rule pack can say is one of these:

    expiry_date > today                     compare two values (dates or numbers)
    expiry_date > today + 6 months          ... with a date offset
    total_salary >= basic_salary            ... between two fields of the same document
    trade_license.name ~= moa.name          the same value across two documents, fuzzily
    iban matches AE## #### #### #### ###    a shape, written as a template or /regex/
    shareholders is present                 the field must have a value
    check: shareholders_have_id             a named check, registered in code

A rule may also carry a `when:` guard, which is one of the same expressions. The rule is only
evaluated if the guard holds. That exists because some rules only make sense in a particular
state: "expires within 30 days" is a useful warning about a valid licence and a nonsense
sentence about one that expired three years ago, where a different rule already fired.

The named check is the honest escape hatch: some rules ("every shareholder has an ID document in
this case") cannot be written as an expression over two values. Those are Python functions in
a registry, and a rule pack refers to one by name. Adding a *rule* is configuration; adding a
new *kind of* check is code, and the difference is visible in the YAML.

Anything the engine cannot evaluate is reported with `evaluated=False` and a reason. It is
never silently treated as a pass — a rule that did not run is not a rule that succeeded.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.agent.extractor import parse_date

# --- expression shapes ---------------------------------------------------------
_CROSS_DOC = re.compile(r"^(\w+)\.(\w+)\s*(~=|==|!=)\s*(\w+)\.(\w+)$")
_COMPARISON = re.compile(r"^(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+)$")
_MATCHES = re.compile(r"^(\w+)\s+matches\s+(.+)$", re.IGNORECASE)
_PRESENT = re.compile(r"^(\w+)\s+is\s+(present|missing)$", re.IGNORECASE)
_OFFSET = re.compile(
    r"^(\w+)\s*([+-])\s*(\d+)\s*(day|days|week|weeks|month|months|year|years)$", re.IGNORECASE
)

# Punctuation is deleted, not turned into a space, so "L.L.C." stays one token and matches
# "LLC". UAE company names use both spellings constantly, and splitting them into "l l c"
# made an identical name look only half similar.
_PUNCTUATION = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE = re.compile(r"\s+")
_NUMBER_LITERAL = re.compile(r"^-?[\d,]+(\.\d+)?$")
_CURRENCY = re.compile(r"\b(aed|usd|dhs|dirhams?)\b", re.IGNORECASE)

_FUZZY_THRESHOLD = 0.7
_DAY_UNITS = {"day": 1, "days": 1, "week": 7, "weeks": 7}
_MONTH_UNITS = {"month": 1, "months": 1, "year": 12, "years": 12}
_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


@dataclass(slots=True)
class RuleOutcome:
    rule_id: str
    passed: bool
    severity: str
    message: str
    policy: str | None
    detail: str
    # False when the rule could not run (missing values, or an expression we do not
    # understand). Callers must not read `passed` as a verdict when this is False.
    evaluated: bool = True
    explain: str = ""
    pack: str = ""
    pack_version: str = ""


# --- named checks --------------------------------------------------------------


@dataclass(slots=True)
class CheckContext:
    """What a named check is allowed to see. Deliberately small."""

    doc_type: str
    own: dict[str, str | None]
    values_by_doc: dict[str, dict[str, str | None]]
    today: date


CheckFn = Callable[[CheckContext], tuple[bool, str]]
_CHECKS: dict[str, CheckFn] = {}


def check(name: str) -> Callable[[CheckFn], CheckFn]:
    """Register a named check so a rule pack can refer to it by name."""

    def register(function: CheckFn) -> CheckFn:
        _CHECKS[name] = function
        return function

    return register


def registered_checks() -> list[str]:
    return sorted(_CHECKS)


@check("shareholders_have_id")
def _shareholders_have_id(context: CheckContext) -> tuple[bool, str]:
    """Every shareholder named in the MOA needs an identity document in the same case.

    This cannot be an expression: it compares a list inside one document against the *set of
    documents* in the case.
    """
    raw = (context.values_by_doc.get("moa") or {}).get("shareholders")
    if not raw:
        return True, "no shareholder list to check"

    shareholders = [part.strip() for part in re.split(r"[;,]", raw) if part.strip()]
    identities = [
        (context.values_by_doc.get("emirates_id") or {}).get("full_name_en"),
        (context.values_by_doc.get("passport") or {}).get("full_name"),
    ]
    known = [name for name in identities if name]
    missing = [
        _strip_percent(person)
        for person in shareholders
        if not any(_similar(person, name) >= _FUZZY_THRESHOLD for name in known)
    ]
    if missing:
        return False, f"no identity document for: {', '.join(missing)}"
    return True, f"all {len(shareholders)} shareholder(s) have an identity document"


@check("shares_total_100")
def _shares_total_100(context: CheckContext) -> tuple[bool, str]:
    """Shareholding percentages, written as "Name 60%; Name 40%", must add up to 100."""
    raw = context.own.get("shareholders")
    if not raw:
        return True, "no shareholder list to check"
    percents = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*%", raw)]
    if not percents:
        return True, "no percentages in the shareholder list"
    total = round(sum(percents), 2)
    return abs(total - 100.0) < 0.01, f"percentages add up to {total}"


# --- helpers -------------------------------------------------------------------


def _strip_percent(value: str) -> str:
    return re.sub(r"\s*\d+(\.\d+)?\s*%", "", value).strip()


def _norm(value: str) -> str:
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub("", value.lower())).strip()


def _similar(left: str, right: str) -> float:
    """Token overlap — enough to catch 'Al Noor Trading LLC' vs 'Al Noor Trading L.L.C.'."""
    a, b = set(_norm(left).split()), set(_norm(right).split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _as_number(value: str) -> float | None:
    cleaned = _CURRENCY.sub("", value).replace(",", "").strip()
    if not _NUMBER_LITERAL.match(cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _add_months(start: date, months: int) -> date:
    """Calendar-correct month arithmetic without pulling in another dependency."""
    index = start.month - 1 + months
    year = start.year + index // 12
    month = index % 12 + 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    last_day = 29 if month == 2 and leap else _DAYS_IN_MONTH[month - 1]
    # Clamp for short months: 31 January plus one month is 28 or 29 February.
    return date(year, month, min(start.day, last_day))


def _resolve(token: str, own: dict[str, str | None], today: date) -> tuple[str, Any] | None:
    """Turn one side of a comparison into a typed value: ("date" | "number" | "text", value)."""
    token = token.strip()

    offset = _OFFSET.match(token)
    if offset:
        base_name, sign, amount_text, unit = offset.groups()
        base = _resolve(base_name, own, today)
        if base is None or base[0] != "date":
            return None
        amount = int(amount_text) * (1 if sign == "+" else -1)
        unit = unit.lower()
        if unit in _DAY_UNITS:
            return "date", base[1] + timedelta(days=amount * _DAY_UNITS[unit])
        return "date", _add_months(base[1], amount * _MONTH_UNITS[unit])

    if token.lower() == "today":
        return "date", today

    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return "text", token[1:-1]

    if _NUMBER_LITERAL.match(token):
        number = _as_number(token)
        if number is not None:
            return "number", number

    raw = own.get(token)
    if raw is None or not raw.strip():
        return None

    parsed_date = parse_date(raw)
    if parsed_date is not None:
        return "date", parsed_date
    number = _as_number(raw)
    if number is not None:
        return "number", number
    return "text", raw


def _compare(kind: str, left: Any, operator: str, right: Any) -> bool:
    if operator == "==":
        if kind == "text":
            return _norm(str(left)) == _norm(str(right))
        return bool(left == right)
    if operator == "!=":
        return not _compare(kind, left, "==", right)
    if kind == "text":
        # Ordering two pieces of text is almost always a mistake in a rule. Say so, do not guess.
        raise TypeError("ordering comparison on text")
    if operator == ">":
        return bool(left > right)
    if operator == "<":
        return bool(left < right)
    if operator == ">=":
        return bool(left >= right)
    return bool(left <= right)


def _template_to_regex(template: str) -> re.Pattern[str]:
    """`784-####-#######-#` becomes a regex: `#` a digit, `@` a letter, the rest literal."""
    if len(template) > 1 and template.startswith("/") and template.endswith("/"):
        return re.compile(template[1:-1])
    parts: list[str] = []
    for char in template:
        if char == "#":
            parts.append(r"\d")
        elif char == "@":
            parts.append("[A-Za-z]")
        elif char == " ":
            # Separators in a written format are optional: "AE07 0331" == "AE070331".
            parts.append(r"[\s-]?")
        else:
            parts.append(re.escape(char))
    return re.compile("^" + "".join(parts) + "$")


# --- the engine ----------------------------------------------------------------


def evaluate(
    rules: list[dict[str, Any]],
    values_by_doc: dict[str, dict[str, str | None]],
    doc_type: str,
    today: date | None = None,
    *,
    pack_id: str = "",
    pack_version: str = "",
) -> list[RuleOutcome]:
    """Run every rule for one document type and report what happened to each one."""
    today = today or date.today()
    own = values_by_doc.get(doc_type, {})
    outcomes: list[RuleOutcome] = []

    for rule in rules:
        rule_id = str(rule.get("id", "UNNAMED"))
        severity = str(rule.get("severity", "warning"))
        message = str(rule.get("message", rule_id))
        policy = rule.get("policy")
        explain = str(rule.get("explain", ""))

        guard = str(rule.get("when", "")).strip()
        if guard:
            guard_result = _run_one({"expr": guard}, own, values_by_doc, doc_type, today)
            if guard_result is None or not guard_result[0]:
                outcomes.append(
                    RuleOutcome(
                        rule_id=rule_id,
                        passed=True,
                        severity=severity,
                        message=message,
                        policy=str(policy) if policy else None,
                        detail=f"not evaluated: the guard {guard!r} does not hold",
                        evaluated=False,
                        explain=explain,
                        pack=pack_id,
                        pack_version=pack_version,
                    )
                )
                continue

        result = _run_one(rule, own, values_by_doc, doc_type, today)
        evaluated = result is not None
        passed, detail = result if result is not None else (
            True,
            "not evaluated: the values this rule needs are missing or the expression is "
            "not supported",
        )
        outcomes.append(
            RuleOutcome(
                rule_id=rule_id,
                passed=passed,
                severity=severity,
                message=message,
                policy=str(policy) if policy else None,
                detail=detail,
                evaluated=evaluated,
                explain=explain,
                pack=pack_id,
                pack_version=pack_version,
            )
        )

    return outcomes


def _run_one(
    rule: dict[str, Any],
    own: dict[str, str | None],
    values_by_doc: dict[str, dict[str, str | None]],
    doc_type: str,
    today: date,
) -> tuple[bool, str] | None:
    named = rule.get("check")
    if named:
        function = _CHECKS.get(str(named))
        if function is None:
            return None
        return function(
            CheckContext(doc_type=doc_type, own=own, values_by_doc=values_by_doc, today=today)
        )

    expr = str(rule.get("expr", "")).strip()
    if not expr:
        return None

    cross = _CROSS_DOC.match(expr)
    if cross:
        left_doc, left_field, operator, right_doc, right_field = cross.groups()
        left = (values_by_doc.get(left_doc) or {}).get(left_field)
        right = (values_by_doc.get(right_doc) or {}).get(right_field)
        if not left or not right:
            return None
        if operator in ("==", "!="):
            same = _norm(left) == _norm(right)
            return (same if operator == "==" else not same), f"{left!r} vs {right!r}"
        score = _similar(left, right)
        return score >= _FUZZY_THRESHOLD, f"{left!r} vs {right!r} (similarity {score:.2f})"

    present = _PRESENT.match(expr)
    if present:
        name, expectation = present.groups()
        has_value = bool((own.get(name) or "").strip())
        passed = has_value if expectation.lower() == "present" else not has_value
        return passed, f"{name} is {'present' if has_value else 'missing'}"

    shape = _MATCHES.match(expr)
    if shape:
        name, template = shape.groups()
        value = own.get(name)
        if not value:
            return None
        pattern = _template_to_regex(template.strip())
        return bool(pattern.match(value.strip())), f"{value!r} against {template.strip()!r}"

    comparison = _COMPARISON.match(expr)
    if comparison:
        left_text, operator, right_text = comparison.groups()
        left = _resolve(left_text, own, today)
        right = _resolve(right_text, own, today)
        if left is None or right is None or left[0] != right[0]:
            return None
        try:
            passed = _compare(left[0], left[1], operator, right[1])
        except TypeError:
            return None
        return passed, f"{left_text.strip()}={left[1]} {operator} {right_text.strip()}={right[1]}"

    return None
