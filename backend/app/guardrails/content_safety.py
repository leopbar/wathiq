"""Content safety.

Azure AI Content Safety scores text in four categories (hate, sexual, violence, self-harm) on
a 0 to 6 severity scale. A KYC document should score zero in all four; anything else means the
upload is not what it claims to be, and a person should see it before the case continues.

DEMO mode uses the local term list below. It is deliberately small and obviously a stand-in —
it is NOT a content classifier, and the UI says so. AZURE mode (M6) calls the real service
behind this same interface and returns the same `SafetyVerdict`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

Category = str

# Indicative terms only. Kept short on purpose: a long word list in a bank repository is a
# liability, and the real classifier replaces this entirely in Azure mode.
_TERMS: dict[Category, list[str]] = {
    "hate": ["kill all", "racial slur", "ethnic cleansing"],
    "violence": ["bomb", "shoot him", "massacre", "behead"],
    "sexual": ["explicit sexual"],
    "self_harm": ["kill myself", "suicide note"],
}

_COMPILED: dict[Category, list[re.Pattern[str]]] = {
    category: [re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE) for term in terms]
    for category, terms in _TERMS.items()
}

# Azure's scale: 0 safe, 2 low, 4 medium, 6 high. We flag at 2 and above.
BLOCK_SEVERITY = 2


@dataclass(slots=True)
class SafetyVerdict:
    flagged: bool
    severities: dict[Category, int] = field(default_factory=dict)
    matches: list[str] = field(default_factory=list)
    engine: str = "demo-term-list-1.0.0"

    @property
    def summary(self) -> str:
        if not self.flagged:
            return "No unsafe content detected"
        worst = max(self.severities, key=lambda key: self.severities[key])
        return f"Flagged: {worst} (severity {self.severities[worst]})"

    def as_dict(self) -> dict[str, object]:
        return {
            "flagged": self.flagged,
            "severities": self.severities,
            "matches": self.matches,
            "engine": self.engine,
        }


def analyse(text: str) -> SafetyVerdict:
    severities: dict[Category, int] = dict.fromkeys(_COMPILED, 0)
    matches: list[str] = []

    for category, patterns in _COMPILED.items():
        hits = sum(1 for pattern in patterns if pattern.search(text))
        if hits:
            # One hit is "low" (2), several is "medium" (4). The real service does this
            # properly; we stay conservative and hand anything flagged to a person.
            severities[category] = 4 if hits > 1 else 2
            matches.append(category)

    flagged = any(value >= BLOCK_SEVERITY for value in severities.values())
    return SafetyVerdict(flagged=flagged, severities=severities, matches=matches)
