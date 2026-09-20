"""Deciding what kind of document each file is.

DEMO mode scores the OCR text against keywords that belong to each document type. It is a
transparent scorer, not a model: you can read why it chose a type, which matters when a
reviewer asks. AZURE mode (M6) swaps in a model call behind the same function.
"""

from __future__ import annotations

from app.db.enums import DocTypeKey

# Words that strongly indicate a type. Weight 2 = a title-level phrase, 1 = a supporting field.
_SIGNALS: dict[DocTypeKey, list[tuple[str, int]]] = {
    DocTypeKey.trade_license: [
        ("trade licence", 3), ("trade license", 3), ("licence number", 2),
        ("license number", 2), ("licensing authority", 2), ("business activity", 1),
        ("legal form", 1),
    ],
    DocTypeKey.emirates_id: [
        ("emirates id", 3), ("identity card", 3), ("id number", 2),
        ("nationality", 1), ("card number", 1),
    ],
    DocTypeKey.passport: [
        ("passport", 3), ("passport number", 2), ("place of birth", 2),
        ("date of birth", 1), ("nationality", 1),
    ],
    DocTypeKey.moa: [
        ("memorandum of association", 3), ("memorandum", 2), ("shareholder", 2),
        ("share capital", 2), ("articles of association", 2),
    ],
    DocTypeKey.salary_certificate: [
        ("salary certificate", 3), ("basic salary", 2), ("gross salary", 2),
        ("employer", 1), ("designation", 1), ("employee", 1),
    ],
}

# Below this, we refuse to guess and mark the document unknown for a human to look at.
_MIN_SCORE = 3


def classify(text: str, filename: str = "") -> tuple[DocTypeKey, float, list[str]]:
    """Return the best document type, a confidence and the evidence behind it.

    The evidence list is kept so the timeline can show *why* a document was classified, rather
    than only what the answer was.
    """
    haystack = f"{text}\n{filename}".lower().replace("_", " ")

    scores: dict[DocTypeKey, int] = {}
    evidence: dict[DocTypeKey, list[str]] = {}
    for doc_type, signals in _SIGNALS.items():
        total = 0
        hits: list[str] = []
        for phrase, weight in signals:
            if phrase in haystack:
                total += weight
                hits.append(phrase)
        if total:
            scores[doc_type] = total
            evidence[doc_type] = hits

    if not scores:
        return DocTypeKey.unknown, 0.0, []

    best = max(scores, key=lambda key: scores[key])
    best_score = scores[best]
    if best_score < _MIN_SCORE:
        return DocTypeKey.unknown, round(best_score / 10, 3), evidence.get(best, [])

    # Confidence reflects how far ahead the winner is, so a close call scores lower.
    runner_up = max((v for k, v in scores.items() if k != best), default=0)
    margin = (best_score - runner_up) / best_score
    confidence = round(min(0.99, 0.55 + 0.44 * margin), 3)
    return best, confidence, evidence[best]
