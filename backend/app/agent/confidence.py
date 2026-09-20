"""Per-field confidence, built from signals instead of guessed.

A single number like "0.87" is useless to a reviewer unless they can see where it came from.
So a field's confidence is assembled from five signals, each of which is a fact about how the
value was obtained:

| signal     | question it answers                                             | weight |
|------------|-----------------------------------------------------------------|--------|
| `ocr`      | How well was the page read at all?                               | 0.20   |
| `grounded` | Does this exact value appear in the document text?               | 0.25   |
| `label`    | Was it found next to its own label, or guessed from nearby text? | 0.15   |
| `shape`    | Does it look like what the schema asks for (date, number, ...)?  | 0.20   |
| `critic`   | Did an independent second read agree?                            | 0.20   |

The weighted average is the **raw** confidence. It is then passed through the calibration
curve (`app.agent.calibration`) to become the **calibrated** confidence, which is the number
the thresholds actually use. Both are stored and both are shown, because they answer different
questions: raw is "how sure is the extractor", calibrated is "how often is the extractor right
when it is this sure".

Every signal keeps a short `detail` string, so the case screen can show the reasoning rather
than a bare percentage.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.agent.extractor import parse_date

_WHITESPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"^-?[\d,]+(\.\d+)?$")
_CURRENCY = re.compile(r"\b(aed|usd|dhs|dirhams?)\b", re.IGNORECASE)
# The characters an OCR engine emits when it could not read a glyph.
_UNREADABLE = ("�", "?")

# Signal weights. They sum to 1.0; a missing signal is dropped and the rest are re-normalised,
# so a field that has not been criticised yet is not punished for it.
WEIGHTS: dict[str, float] = {
    "ocr": 0.20,
    "grounded": 0.25,
    "label": 0.15,
    "shape": 0.20,
    "critic": 0.20,
}

SIGNAL_LABELS: dict[str, str] = {
    "ocr": "Page read quality",
    "grounded": "Found in the document text",
    "label": "Next to its own label",
    "shape": "Matches the expected format",
    "critic": "Second read agreed",
}

# Each self-correction attempt the worker needed costs a little confidence: the value is fine
# now, but the first answer was not, which is itself evidence.
SELF_CORRECTION_PENALTY = 0.05


@dataclass(slots=True)
class Signal:
    key: str
    label: str
    value: float
    weight: float
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Breakdown:
    raw: float
    signals: list[Signal] = field(default_factory=list)
    penalty: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "penalty": self.penalty,
            "signals": [signal.as_dict() for signal in self.signals],
        }

    @property
    def weakest(self) -> Signal | None:
        """The signal dragging the score down — what the reviewer should look at first."""
        return min(self.signals, key=lambda signal: signal.value, default=None)


def _normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().lower()


def grounding(value: str | None, document_text: str) -> Signal:
    """Is the value actually in the document, or did something invent it?

    This is the single most important assurance signal in the whole system: a value that
    cannot be found in the source text must never be auto-accepted.
    """
    if not value:
        return Signal("grounded", SIGNAL_LABELS["grounded"], 0.0, WEIGHTS["grounded"],
                      "no value to ground")
    haystack = _normalise(document_text)
    needle = _normalise(value)
    if needle and needle in haystack:
        return Signal("grounded", SIGNAL_LABELS["grounded"], 1.0, WEIGHTS["grounded"],
                      "exact text found in the document")

    # Partial grounding: most of the words are there, which happens when OCR split a line.
    words = [word for word in needle.split() if len(word) > 2]
    if words:
        present = sum(1 for word in words if word in haystack)
        ratio = present / len(words)
        if ratio >= 0.5:
            return Signal("grounded", SIGNAL_LABELS["grounded"], round(ratio, 3),
                          WEIGHTS["grounded"], f"{present} of {len(words)} words found")
    return Signal("grounded", SIGNAL_LABELS["grounded"], 0.0, WEIGHTS["grounded"],
                  "value not found in the document text")


def shape(value: str | None, expected_type: str) -> Signal:
    """Does the value look like the type the schema asks for?"""
    weight = WEIGHTS["shape"]
    if not value:
        return Signal("shape", SIGNAL_LABELS["shape"], 0.0, weight, "no value")

    cleaned = value.strip()
    if expected_type == "date":
        parsed = parse_date(cleaned)
        return Signal("shape", SIGNAL_LABELS["shape"], 1.0 if parsed else 0.0, weight,
                      f"parsed as {parsed}" if parsed else "not a recognisable date")
    if expected_type == "number":
        stripped = _CURRENCY.sub("", cleaned).replace(",", "").strip()
        ok = bool(_NUMBER.match(stripped))
        return Signal("shape", SIGNAL_LABELS["shape"], 1.0 if ok else 0.0, weight,
                      "numeric" if ok else "not a number")
    if expected_type == "list":
        parts = [part for part in re.split(r"[;,]", cleaned) if part.strip()]
        ok = len(parts) >= 1
        return Signal("shape", SIGNAL_LABELS["shape"], 1.0 if ok else 0.3, weight,
                      f"{len(parts)} item(s)")

    # Free text: judged on legibility, since there is no format to check against.
    unreadable = sum(cleaned.count(char) for char in _UNREADABLE)
    if unreadable:
        value_score = max(0.1, 1.0 - 0.3 * unreadable)
        return Signal("shape", SIGNAL_LABELS["shape"], round(value_score, 3), weight,
                      f"{unreadable} unreadable character(s)")
    if len(cleaned) < 2:
        return Signal("shape", SIGNAL_LABELS["shape"], 0.4, weight, "suspiciously short")
    return Signal("shape", SIGNAL_LABELS["shape"], 1.0, weight, "plain readable text")


def ocr_signal(ocr_confidence: float) -> Signal:
    return Signal("ocr", SIGNAL_LABELS["ocr"], round(ocr_confidence, 3), WEIGHTS["ocr"],
                  f"page read at {ocr_confidence:.0%}")


def label_signal(matched_label: bool, source_text: str | None) -> Signal:
    if matched_label:
        return Signal("label", SIGNAL_LABELS["label"], 1.0, WEIGHTS["label"],
                      f"read under {source_text!r}" if source_text else "label matched")
    return Signal("label", SIGNAL_LABELS["label"], 0.3, WEIGHTS["label"],
                  "no matching label in the document")


def critic_signal(agreed: bool | None, detail: str = "") -> Signal | None:
    """`None` means the critic has not looked yet — a missing signal, not a bad one."""
    if agreed is None:
        return None
    return Signal("critic", SIGNAL_LABELS["critic"], 1.0 if agreed else 0.0, WEIGHTS["critic"],
                  detail or ("agreed" if agreed else "disagreed"))


def combine(signals: list[Signal], *, self_corrections: int = 0) -> Breakdown:
    """Weighted average of the signals that exist, minus the self-correction penalty."""
    present = [signal for signal in signals if signal is not None]
    total_weight = sum(signal.weight for signal in present)
    if total_weight <= 0:
        return Breakdown(raw=0.0, signals=present, penalty=0.0)

    weighted = sum(signal.value * signal.weight for signal in present) / total_weight
    penalty = round(SELF_CORRECTION_PENALTY * self_corrections, 3)
    raw = round(max(0.0, min(1.0, weighted - penalty)), 3)
    return Breakdown(raw=raw, signals=present, penalty=penalty)


def from_dicts(raw_signals: list[dict[str, Any]]) -> list[Signal]:
    """Rebuild signals that were checkpointed as plain dictionaries."""
    return [
        Signal(
            key=str(item["key"]),
            label=str(item.get("label", SIGNAL_LABELS.get(str(item["key"]), item["key"]))),
            value=float(item.get("value", 0.0)),
            weight=float(item.get("weight", WEIGHTS.get(str(item["key"]), 0.0))),
            detail=str(item.get("detail", "")),
        )
        for item in raw_signals
    ]


def describe() -> list[dict[str, Any]]:
    """The signal table, for the UI and the docs."""
    return [
        {"key": key, "label": SIGNAL_LABELS[key], "weight": weight}
        for key, weight in WEIGHTS.items()
    ]
