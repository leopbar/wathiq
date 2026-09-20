"""The critic: a second opinion on what the extractor produced (actor-critic).

The extractor is the *actor*: it reads a document and proposes values. The critic's job is to
try to knock those values down. It is useful only because it works differently from the actor —
a second pass with the same method would agree with itself every time and tell us nothing.

Three challenges, in order of how much they matter:

1. **Grounding.** Is this exact string on the page? The critic does not take the extractor's
   word for where the value came from; where the document-store MCP server is reachable it
   asks *that* — the file on disk — rather than the text already in the state. A value that
   cannot be found on the page is the single strongest reason to distrust it.
2. **Shape.** Does the value look like what the schema asked for?
3. **Wrong-neighbour.** Is the value sitting under a *different* field's label? This catches
   the most common real extraction error, which is not a misread character but a value taken
   from the line above or below the right one.

A disagreement does not overrule the extractor. It lowers the field's confidence (the critic
is one of the five confidence signals) and, on a critical field, sends the case to a human.
The critic never silently rewrites a value: where it has a better candidate it *suggests* it,
and a person decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.agent.extractor import parse_date
from app.agent.tools import ToolBroker

_NORMALISE = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"^-?[\d,]+(\.\d+)?$")
_CURRENCY = re.compile(r"\b(aed|usd|dhs|dirhams?)\b", re.IGNORECASE)


def _key(text: str) -> str:
    return _NORMALISE.sub(" ", text.lower()).strip()


def _flat(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().lower()


@dataclass(slots=True)
class Verdict:
    field: str
    agreed: bool
    reason: str
    via: str
    suggested_value: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "agreed": self.agreed,
            "reason": self.reason,
            "via": self.via,
            "suggested_value": self.suggested_value,
        }


def _shape_ok(value: str, expected: str) -> bool:
    if expected == "date":
        return parse_date(value) is not None
    if expected == "number":
        return bool(_NUMBER.match(_CURRENCY.sub("", value).replace(",", "").strip()))
    return True


def _wrong_neighbour(
    value: str, field_name: str, lines: list[str], label_keys: dict[str, str]
) -> str | None:
    """If the value sits under another field's label, name that other field."""
    flat_value = _flat(value)
    for index, line in enumerate(lines):
        if _flat(line) != flat_value:
            continue
        if index == 0:
            continue
        owner = label_keys.get(_key(lines[index - 1]))
        if owner and owner != field_name:
            return owner
    return None


async def review_field(
    field: dict[str, Any],
    *,
    document: dict[str, Any],
    expected_type: str,
    label_keys: dict[str, str],
    broker: ToolBroker | None = None,
) -> Verdict:
    """Challenge one extracted value."""
    name = str(field["name"])
    value = field.get("value")
    text = str(document.get("safe_text") or document.get("ocr_text") or "")
    lines = text.split("\n")

    if not value:
        # An empty field is not a disagreement. The extractor said "not present", and the
        # critic has nothing to contradict.
        return Verdict(name, True, "no value proposed", "none")

    # 1. Grounding, preferably against the file itself rather than the state.
    via = "local"
    grounded = _flat(value) in _flat(text)
    if broker is not None and broker.available("document_store"):
        call = await broker.call(
            "document_store",
            "find_in_document",
            path=str(document.get("storage_path", "")),
            value=str(value),
        )
        if call.ok and (call.result or {}).get("checked"):
            grounded = bool((call.result or {}).get("found"))
            via = "mcp:document_store"

    if not grounded:
        return Verdict(
            name,
            False,
            f"{value!r} could not be found in the document itself",
            via,
        )

    # 2. Shape.
    if not _shape_ok(str(value), expected_type):
        return Verdict(
            name,
            False,
            f"{value!r} is not a valid {expected_type}",
            via,
        )

    # 3. Wrong neighbour.
    owner = _wrong_neighbour(str(value), name, lines, label_keys)
    if owner:
        return Verdict(
            name,
            False,
            f"this value appears under the {owner!r} label, not {name!r}",
            via,
        )

    return Verdict(name, True, "found in the document under its own label", via)


def label_index(field_schema: list[dict[str, Any]]) -> dict[str, str]:
    """Every label spelling we know, mapped to the field it belongs to."""
    index: dict[str, str] = {}
    for spec in field_schema:
        name = str(spec["name"])
        for candidate in (name, name.replace("_", " "), spec.get("label_en"), spec.get("label_ar")):
            if candidate:
                index[_key(str(candidate))] = name
    return index
