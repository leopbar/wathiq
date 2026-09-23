"""Case-type profiles: what a kind of case is, written as data.

A case type (a corporate KYC refresh, a salary certificate for a loan) differs from another in
four ways only, and each one is a line in a YAML file in this folder, not a branch in the
engine:

* **expected documents** — what the intake screen asks for;
* **posting** — which core-banking tool records the approved result, and what that record is
  called. The idempotency key includes the record name, so two use cases can never collide;
* **registry checks** — which names on which documents must be a registered, active company;
* **customer kind** — whose file the result is written to (a company, or a person).

Adding a third use case is: one profile here, one document type, one rule pack, one prompt.
The graph, the process workflow and the posting step do not change. The profile's version is
recorded with the posting, so an audit can read a case against the profile that ran it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROFILE_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class RegistryCheck:
    """A name on a document that must belong to a registered, trading company."""

    document: str
    field: str
    role: str
    policy: str


@dataclass(frozen=True, slots=True)
class CaseProfile:
    id: str
    version: str
    title_en: str
    title_ar: str
    customer_kind: str
    expected_documents: list[str]
    posting_tool: str
    posting_record: str
    required_fields: list[str] = field(default_factory=list)
    registry_checks: list[RegistryCheck] = field(default_factory=list)
    source: str = ""

    @property
    def reference(self) -> str:
        return f"{self.id}@{self.version}"


def _load_one(path: Path) -> CaseProfile:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    posting = raw.get("posting") or {}
    return CaseProfile(
        id=str(raw["id"]),
        version=str(raw.get("version", "0.0.0")),
        title_en=str(raw.get("title_en", raw["id"])),
        title_ar=str(raw.get("title_ar", "")),
        customer_kind=str(raw.get("customer_kind", "corporate")),
        expected_documents=[str(item) for item in raw.get("expected_documents", [])],
        posting_tool=str(posting["tool"]),
        posting_record=str(posting["record"]),
        required_fields=[str(item) for item in posting.get("required_fields", [])],
        registry_checks=[
            RegistryCheck(
                document=str(check["document"]),
                field=str(check["field"]),
                role=str(check.get("role", "company")),
                policy=str(check.get("policy", "")),
            )
            for check in raw.get("registry_checks", [])
        ],
        source=path.name,
    )


@lru_cache(maxsize=1)
def load_profiles() -> dict[str, CaseProfile]:
    """Every profile on disk, keyed by case type. A malformed file fails loudly at startup:
    a case type whose posting destination cannot be read must not quietly post elsewhere."""
    return {
        profile.id: profile
        for profile in (_load_one(path) for path in sorted(PROFILE_DIR.glob("*.yaml")))
    }


def profile_for(case_type: str) -> CaseProfile:
    """The profile for a case type. Unknown types raise: there is no default destination."""
    profiles = load_profiles()
    try:
        return profiles[case_type]
    except KeyError:
        raise KeyError(
            f"No case-type profile for {case_type!r}; have {sorted(profiles)}"
        ) from None
