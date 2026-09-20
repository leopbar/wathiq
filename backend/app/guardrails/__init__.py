"""Guardrails: everything that runs *before* a model sees a document, and *after* it answers.

Four checks, in this order:

1. **Prompt shield** — is there an instruction hidden in the document? (`shield`)
2. **Content safety** — is this document something a KYC file should not contain?
   (`content_safety`)
3. **PII tokenisation** — replace identifiers with tokens before anything is logged. (`pii`)
4. **Output sanitisation** — clean every value on the way back out. (`sanitise`)

`screen()` runs 1 to 3 over one document and returns a report. The report is JSON-serialisable
because it is written into the LangGraph state and checkpointed. The vault holding the real
PII values is deliberately NOT part of it — it stays in memory for the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.guardrails import content_safety, pii, sanitise, shield

__all__ = [
    "GuardrailReport",
    "content_safety",
    "pii",
    "sanitise",
    "screen",
    "shield",
]


@dataclass(slots=True)
class GuardrailReport:
    """What the guardrails found in one document, and the two copies of its text.

    The two copies are not interchangeable, and mixing them up is a real bug rather than a
    style point:

    * `clean_text` — invisible characters, bidi overrides and markup removed. This is what the
      **pipeline** reads. The values in it are the customer's real values, because extracting a
      date of birth from `<DOB_1>` is not extraction.
    * `log_text` — `clean_text` with every identifier replaced by a token. This is what may be
      written to a **log, a trace or an evaluation fixture**, and nothing else may be.
    """

    document_id: str
    filename: str
    injection: dict[str, Any]
    safety: dict[str, Any]
    pii_counts: dict[str, int]
    sanitised: bool
    clean_text: str = ""
    log_text: str = ""

    @property
    def blocked(self) -> bool:
        """Blocked means 'a person must look', never 'throw the document away'."""
        return bool(self.injection.get("attacked")) or bool(self.safety.get("flagged"))

    def as_dict(self) -> dict[str, Any]:
        """The form stored in the graph state. Neither copy of the text is included."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "injection": self.injection,
            "safety": self.safety,
            "pii_counts": self.pii_counts,
            "sanitised": self.sanitised,
            "blocked": self.blocked,
        }


def screen(document_id: str, filename: str, text: str) -> tuple[GuardrailReport, pii.PiiVault]:
    """Run every input guardrail over one document's text.

    Returns the report and the PII vault. The caller keeps the vault in memory so tokens can be
    turned back into values for the reviewer's screen, and never writes it down.
    """
    verdict = shield.inspect(text)
    safety = content_safety.analyse(text)

    # What the pipeline reads: invisible characters gone, markup gone, values intact.
    neutralised = shield.neutralise(text)
    cleaned = sanitise.sanitise_text(neutralised)
    # What a log, a trace or an eval fixture may contain: identifiers replaced with tokens.
    log_text, vault = pii.tokenise(cleaned)

    report = GuardrailReport(
        document_id=document_id,
        filename=filename,
        injection=verdict.as_dict(),
        safety=safety.as_dict(),
        pii_counts=vault.summary,
        sanitised=sanitise.changed(text, cleaned),
        clean_text=cleaned,
        log_text=log_text,
    )
    return report, vault


def describe() -> list[dict[str, Any]]:
    """What each guardrail is and how it is implemented right now — used by the UI, honestly."""
    return [
        {
            "key": "prompt_shield",
            "name": "Prompt shield",
            "purpose": "Detects instructions hidden inside a document before any model call.",
            "implementation": f"Local pattern set ({shield.ShieldVerdict(False, 0.0).engine})",
            "azure": "Azure AI Prompt Shields (M6) — both verdicts combined, either one wins.",
        },
        {
            "key": "content_safety",
            "name": "Content safety",
            "purpose": "Checks the upload is not hate, violence, sexual or self-harm content.",
            "implementation": "Local term list — a stand-in, not a classifier.",
            "azure": "Azure AI Content Safety (M6), four categories on a 0 to 6 severity scale.",
        },
        {
            "key": "pii",
            "name": "PII tokenisation",
            "purpose": "Replaces identifiers with tokens before anything is logged or traced.",
            "implementation": (
                f"{len(pii.RECOGNISER_DESCRIPTIONS)} local recognisers "
                "(Emirates ID, UAE IBAN, passport, card, phone, email, date)."
            ),
            "azure": "Microsoft Presidio with the same custom recognisers registered (M6).",
        },
        {
            "key": "sanitiser",
            "name": "Output sanitisation",
            "purpose": "Strips HTML, scripts, bidi overrides and zero-width characters.",
            "implementation": "Runs in every mode, on every value we store.",
            "azure": "Unchanged — this one is ours, not a service.",
        },
    ]
