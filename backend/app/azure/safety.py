"""Azure AI Content Safety: Prompt Shields and the four-category classifier.

Two REST calls behind the two guardrails M3 built as local stand-ins:

* `shield_prompt()` → `POST /contentsafety/text:shieldPrompt` — Microsoft's own detector for
  instructions hidden in content. The document goes in the `documents` array, never in
  `userPrompt`: that is the service's own distinction between "what the operator asked" and
  "untrusted material the operator is showing the model", and it is the same distinction the
  whole guardrail layer is built on.
* `analyse_text()` → `POST /contentsafety/text:analyze` — hate, sexual, violence and self-harm
  on the 0 to 6 severity scale the local term list has been imitating since M3.

**Both verdicts are combined with the local ones; neither replaces them.** The local shield
still runs, and if *either* says "attack" the case goes to a person. Two detectors with
different failure modes catch more than the better one alone, and the local one keeps working
when the service is unreachable. (DECISIONS #67)

**Why `httpx` rather than the Content Safety SDK.** Prompt Shields moves between preview API
versions faster than the SDK follows, and `httpx` is already a dependency with an async client
the rest of the app uses. Two small, explicit POST bodies are easier to read — and to fake in a
test — than a wrapper whose model classes change shape between releases. (DECISIONS #68)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.azure.credentials import token_credential
from app.core.config import settings
from app.guardrails.content_safety import BLOCK_SEVERITY, SafetyVerdict
from app.guardrails.shield import ShieldSignal, ShieldVerdict

logger = logging.getLogger(__name__)

# Pinned. An API version that moves on its own would change a guardrail's behaviour without a
# code review, which is the one place that must never happen quietly.
API_VERSION = "2024-09-01"
_SCOPE = "https://cognitiveservices.azure.com/.default"

# The service's category names, mapped to the keys `SafetyVerdict` already uses.
_CATEGORY_KEYS = {
    "Hate": "hate",
    "Sexual": "sexual",
    "Violence": "violence",
    "SelfHarm": "self_harm",
}

# Prompt Shields rejects a document above this length. Truncating is the right behaviour: the
# local shield has already seen the whole text, so a long document is still fully inspected by
# one of the two detectors, and we say in the verdict that this one saw only part.
_MAX_DOCUMENT_CHARS = 10_000


class ContentSafetyUnavailable(RuntimeError):
    """The service is configured but did not answer.

    Raised so the caller can decide. The guardrail layer treats it as "could not check", which
    is recorded on the case and is a different outcome from "checked and found nothing" — the
    distinction the whole system is built on.
    """


def _headers() -> dict[str, str]:
    key = settings.azure_content_safety_key.strip()
    if key:
        return {"Ocp-Apim-Subscription-Key": key}
    token = token_credential().get_token(_SCOPE).token
    return {"Authorization": f"Bearer {token}"}


def _url(operation: str) -> str:
    base = settings.azure_content_safety_endpoint.strip().rstrip("/")
    return f"{base}/contentsafety/text:{operation}?api-version={API_VERSION}"


async def _post(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=settings.mcp_timeout_seconds) as client:
            response = await client.post(_url(operation), json=payload, headers=_headers())
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise ContentSafetyUnavailable(f"Content Safety {operation} failed: {exc}") from exc


async def shield_prompt(text: str) -> ShieldVerdict:
    """Ask Prompt Shields whether this document contains an attack.

    Returns a `ShieldVerdict` — the same shape the local shield returns — so the caller can
    combine the two without knowing which detector produced which.
    """
    truncated = text[:_MAX_DOCUMENT_CHARS]
    payload = {"userPrompt": "", "documents": [truncated]}
    body = await _post("shieldPrompt", payload)

    analyses = body.get("documentsAnalysis") or []
    attacked = any(bool(item.get("attackDetected")) for item in analyses)
    # The service reports a boolean, not a score. Inventing a number between 0 and 1 would be
    # a fabrication, so the risk is the boolean expressed plainly.
    risk = 1.0 if attacked else 0.0

    signals: list[ShieldSignal] = []
    if attacked:
        signals.append(
            ShieldSignal(
                kind="prompt-shield",
                pattern="Azure AI Prompt Shields",
                excerpt=(
                    "the service flagged an indirect prompt injection in this document"
                    + (
                        f" (first {_MAX_DOCUMENT_CHARS} characters inspected)"
                        if len(text) > _MAX_DOCUMENT_CHARS
                        else ""
                    )
                ),
            )
        )
    return ShieldVerdict(
        attacked=attacked,
        risk=risk,
        signals=signals,
        engine=f"azure-prompt-shields@{API_VERSION}",
    )


async def analyse_text(text: str) -> SafetyVerdict:
    """Ask Content Safety to score the four categories."""
    body = await _post("analyze", {"text": text[:_MAX_DOCUMENT_CHARS]})

    severities: dict[str, int] = dict.fromkeys(_CATEGORY_KEYS.values(), 0)
    for item in body.get("categoriesAnalysis") or []:
        key = _CATEGORY_KEYS.get(str(item.get("category", "")))
        if key is not None:
            severities[key] = int(item.get("severity", 0) or 0)

    matches = [key for key, value in severities.items() if value >= BLOCK_SEVERITY]
    return SafetyVerdict(
        flagged=bool(matches),
        severities=severities,
        matches=matches,
        engine=f"azure-content-safety@{API_VERSION}",
    )


def combine_shield(local: ShieldVerdict, remote: ShieldVerdict | None) -> ShieldVerdict:
    """Both detectors' findings in one verdict. Either one flagging is enough.

    Not an average and not a vote. These are detectors for a deliberate attack, so a miss costs
    far more than a false alarm — and a false alarm here means one extra pair of human eyes on
    a KYC file, which is cheap.
    """
    if remote is None:
        return local
    return ShieldVerdict(
        attacked=local.attacked or remote.attacked,
        risk=max(local.risk, remote.risk),
        signals=[*local.signals, *remote.signals],
        engine=f"{local.engine}+{remote.engine}",
    )


def combine_safety(local: SafetyVerdict, remote: SafetyVerdict | None) -> SafetyVerdict:
    """The higher severity per category wins, for the same reason."""
    if remote is None:
        return local
    categories = set(local.severities) | set(remote.severities)
    severities = {
        key: max(local.severities.get(key, 0), remote.severities.get(key, 0))
        for key in categories
    }
    matches = sorted({key for key, value in severities.items() if value >= BLOCK_SEVERITY})
    return SafetyVerdict(
        flagged=bool(matches),
        severities=severities,
        matches=matches,
        engine=f"{local.engine}+{remote.engine}",
    )


__all__ = [
    "API_VERSION",
    "ContentSafetyUnavailable",
    "analyse_text",
    "combine_safety",
    "combine_shield",
    "shield_prompt",
]
