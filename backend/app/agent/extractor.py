"""Turning OCR text into typed fields.

DEMO mode uses `DemoExtractor`: a deterministic, offline reader. It does NOT use a language
model — it matches the labels the document actually contains and reads the value next to them.
That is honest for a demo (it never invents a value) and it makes the whole pipeline
reproducible, which is what the Quality Lab in M5 needs.

AZURE mode (M6) plugs a Foundry call with structured outputs behind the same interface. The
Pydantic validation of the result stays identical, so only the source of the values changes.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

# Field values we recognise without any model, by shape.
_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "%Y-%m-%d"),
    (re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"), "%d/%m/%Y"),
]
_NORMALISE = re.compile(r"[^\w]+")


def _key(text: str) -> str:
    return _NORMALISE.sub(" ", text.lower()).strip()


@dataclass(slots=True)
class ExtractedValue:
    value: str | None
    confidence: float
    source_text: str | None = None
    page: int | None = None


def parse_date(text: str) -> date | None:
    """Read a date in either of the two formats the synthetic documents use."""
    for pattern, _fmt in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groups()
        try:
            if len(groups[0]) == 4:
                return date(int(groups[0]), int(groups[1]), int(groups[2]))
            return date(int(groups[2]), int(groups[1]), int(groups[0]))
        except ValueError:
            return None
    return None


class ExtractorBackend(ABC):
    """Turning a document's lines into values.

    `prompt` and `examples` were added in M6 and are keyword-only with defaults, so every
    existing call site still works unchanged. A deterministic reader has no use for either;
    a model-backed one needs both, and the alternative — reaching into the database from
    inside the extractor — would put an I/O dependency in the one place that has to stay
    pure enough to run in a test without a database.
    """

    @abstractmethod
    def extract(
        self,
        lines: list[str],
        field_schema: list[dict[str, object]],
        doc_type: str,
        *,
        prompt: str | None = None,
        examples: list[dict[str, object]] | None = None,
    ) -> dict[str, ExtractedValue]: ...

    @property
    @abstractmethod
    def label(self) -> str: ...

    @property
    @abstractmethod
    def model_version(self) -> str: ...


class DemoExtractor(ExtractorBackend):
    """Label-and-value reader over the OCR lines.

    The synthetic documents are laid out as LABEL on one line and the value on the next, which
    is how `services/pdf.py` writes them. We match the label against the field schema and take
    the following line as the value.
    """

    def extract(
        self,
        lines: list[str],
        field_schema: list[dict[str, object]],
        doc_type: str,
        *,
        prompt: str | None = None,
        examples: list[dict[str, object]] | None = None,
    ) -> dict[str, ExtractedValue]:
        # `prompt` and `examples` are accepted and ignored: this reader matches labels and
        # makes no model call, so wording cannot change its answer. That is the honest reason
        # the M5 sensitivity harness reports "unsupported" in demo mode rather than a score.
        del prompt, examples
        # Map every label spelling we know to the schema field name.
        label_to_name: dict[str, str] = {}
        for spec in field_schema:
            name = str(spec["name"])
            label_to_name[_key(name)] = name
            label_to_name[_key(name.replace("_", " "))] = name
            for label_key in ("label_en", "label_ar"):
                label = spec.get(label_key)
                if label:
                    label_to_name[_key(str(label))] = name

        found: dict[str, ExtractedValue] = {}
        for index, line in enumerate(lines):
            name = label_to_name.get(_key(line))
            if name is None or name in found:
                continue
            value = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if not value or _key(value) in label_to_name:
                # The next line is another label, so this field is present but empty.
                found[name] = ExtractedValue(None, 0.0, source_text=line)
                continue
            found[name] = ExtractedValue(
                value=value,
                confidence=self._confidence(value),
                source_text=line,
                page=1,
            )
        return found

    @staticmethod
    def _confidence(value: str) -> float:
        """A deterministic, explainable confidence — never a random number.

        Clean, well-formed values score high; short, noisy or replacement-character values
        score low, which is what sends a field to human review.
        """
        score = 0.93
        if "?" in value or "�" in value:
            score -= 0.35  # OCR replacement characters: the value is doubtful
        if len(value) < 3:
            score -= 0.15
        if len(value) > 60:
            score -= 0.05
        if any(ch.isdigit() for ch in value) and any(ch.isalpha() for ch in value):
            score += 0.02  # mixed reference numbers are the documents' most reliable field
        return round(max(0.05, min(0.99, score)), 3)

    @property
    def label(self) -> str:
        return "Demo extractor (deterministic label reader, no model call)"

    @property
    def model_version(self) -> str:
        return "demo-extractor-1.0.0"


_backend: ExtractorBackend | None = None


def get_extractor() -> ExtractorBackend:
    """The extractor this deployment is configured for.

    Foundry only when both its endpoint and a deployment name are set. The import is inside
    the branch so demo mode never loads an Azure SDK.
    """
    global _backend
    if _backend is None:
        from app.core.config import settings

        if settings.foundry_enabled:
            from app.azure.foundry import FoundryExtractor

            _backend = FoundryExtractor()
        else:
            _backend = DemoExtractor()
    return _backend


def reset_extractor() -> None:
    """Drop the cached backend so a test can change the settings and pick a different one."""
    global _backend
    _backend = None
