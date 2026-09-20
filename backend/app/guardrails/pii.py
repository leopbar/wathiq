"""PII tokenisation.

Rule for this project: personal data may live in the case record, which is access-controlled
and audited. It must NOT leak into logs, traces, event details or evaluation data, because
those are read by engineers and copied into test fixtures.

So anything on its way to one of those places goes through `tokenise()` first. Each detected
value is replaced with a stable label like `<EID_1>`. The mapping lives in a `PiiVault` that
stays in memory for the length of one case run and is never written anywhere.

DEMO mode uses the recognisers below: deterministic, offline, no model. They cover the
identifiers that actually appear in UAE banking documents. AZURE mode (M6) adds Microsoft
Presidio with the same custom recognisers registered, behind this same interface — Presidio
needs a spaCy model, which is a 500 MB dependency we do not want in the demo image.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- recognisers ---------------------------------------------------------------
# Each one is (label, regex, description). Order matters: the most specific first, so an
# Emirates ID is not first matched by the generic long-number recogniser.
_RECOGNISERS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "EID",
        re.compile(r"\b784-?\d{4}-?\d{7}-?\d\b"),
        "Emirates ID (784-YYYY-NNNNNNN-C)",
    ),
    (
        "IBAN",
        re.compile(r"\bAE\d{2}[\s-]?(?:\d{4}[\s-]?){4}\d{3}\b", re.IGNORECASE),
        "UAE IBAN (AE + 21 digits)",
    ),
    (
        "PASSPORT",
        re.compile(r"\b[A-Z]{1,2}\d{6,8}\b"),
        "Passport number",
    ),
    (
        "EMAIL",
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
        "Email address",
    ),
    (
        "PHONE",
        re.compile(r"(?:\+971|00971|0)\s?5\d(?:[\s-]?\d){7}\b"),
        "UAE mobile number",
    ),
    (
        "CARD",
        re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"),
        "Payment card number",
    ),
    (
        "DOB",
        re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),
        "Date (treated as a date of birth when it appears near a person)",
    ),
]

RECOGNISER_DESCRIPTIONS: list[dict[str, str]] = [
    {"label": label, "pattern": pattern.pattern, "description": description}
    for label, pattern, description in _RECOGNISERS
]


@dataclass(slots=True)
class PiiHit:
    label: str
    token: str
    start: int
    end: int


@dataclass
class PiiVault:
    """Token → original value, for one case run only.

    Never persisted, never logged. `restore()` exists so a reviewer's screen can show the real
    value after the record has been read from the access-controlled table.
    """

    mapping: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def token_for(self, label: str, value: str) -> str:
        """The same value always gets the same token, so a document stays readable."""
        for token, stored in self.mapping.items():
            if stored == value and token.startswith(f"<{label}_"):
                return token
        self.counts[label] = self.counts.get(label, 0) + 1
        token = f"<{label}_{self.counts[label]}>"
        self.mapping[token] = value
        return token

    def restore(self, text: str) -> str:
        result = text
        for token, value in self.mapping.items():
            result = result.replace(token, value)
        return result

    @property
    def summary(self) -> dict[str, int]:
        """What was found, by type — safe to log, because it holds no values."""
        return dict(self.counts)


def detect(text: str) -> list[PiiHit]:
    """Find personal identifiers, longest match first, without overlapping."""
    hits: list[PiiHit] = []
    taken: list[tuple[int, int]] = []

    for label, pattern, _description in _RECOGNISERS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < t_end and end > t_start for t_start, t_end in taken):
                continue
            taken.append((start, end))
            hits.append(PiiHit(label=label, token="", start=start, end=end))

    return sorted(hits, key=lambda hit: hit.start)


def tokenise(text: str, vault: PiiVault | None = None) -> tuple[str, PiiVault]:
    """Replace every recognised identifier with a stable token.

    Returns the safe text and the vault. Anything written to a log, a trace, an event detail
    or an eval fixture must be the safe text.
    """
    vault = vault or PiiVault()
    hits = detect(text)
    if not hits:
        return text, vault

    pieces: list[str] = []
    cursor = 0
    for hit in hits:
        pieces.append(text[cursor : hit.start])
        pieces.append(vault.token_for(hit.label, text[hit.start : hit.end]))
        cursor = hit.end
    pieces.append(text[cursor:])
    return "".join(pieces), vault


def redact(value: str | None) -> str | None:
    """A one-shot tokenisation for a single value, when no vault is needed."""
    if value is None:
        return None
    safe, _vault = tokenise(value)
    return safe
