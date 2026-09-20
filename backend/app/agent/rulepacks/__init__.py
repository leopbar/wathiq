"""Loading the versioned YAML rule packs.

A rule pack is one YAML file in `app/agent/rulepacks/`. It carries an id, a semantic version
and the rules for one document type. Keeping them as files (not rows) means:

* every change to a bank rule is a diff in a pull request, reviewed like code;
* the version that judged a case is recorded on the case, so an audit two years later can be
  read against the rules that were in force at the time;
* onboarding a new document type is adding a file, not editing the engine.

The database still holds `document_types.rules`. That is the Settings screen's editable copy
and the fallback: if no pack covers a document type, the engine runs the rows instead and says
so. One source at a time, never both, and the case records which one ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PACK_DIR = Path(__file__).parent


@dataclass(slots=True)
class RulePack:
    id: str
    version: str
    title: str
    description: str
    applies_to: list[str]
    rules: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""

    @property
    def reference(self) -> str:
        """How a pack is named on a finding: `trade_license@1.2.0`."""
        return f"{self.id}@{self.version}"


def _load_one(path: Path) -> RulePack | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(raw, dict) or "id" not in raw:
        return None
    return RulePack(
        id=str(raw["id"]),
        version=str(raw.get("version", "0.0.0")),
        title=str(raw.get("title", raw["id"])),
        description=str(raw.get("description", "")).strip(),
        applies_to=[str(item) for item in raw.get("applies_to", [])] or [str(raw["id"])],
        rules=[rule for rule in raw.get("rules", []) if isinstance(rule, dict)],
        source=path.name,
    )


@lru_cache(maxsize=1)
def load_packs() -> dict[str, RulePack]:
    """Every pack on disk, keyed by its id. Cached: the files do not change at runtime."""
    packs: dict[str, RulePack] = {}
    if not PACK_DIR.is_dir():
        return packs
    for path in sorted(PACK_DIR.glob("*.yaml")):
        pack = _load_one(path)
        if pack is not None:
            packs[pack.id] = pack
    return packs


@lru_cache(maxsize=1)
def _by_doc_type() -> dict[str, RulePack]:
    index: dict[str, RulePack] = {}
    for pack in load_packs().values():
        for doc_type in pack.applies_to:
            index[doc_type] = pack
    return index


def pack_for(doc_type: str) -> RulePack | None:
    """The pack that governs this document type, or None if the database rows should run."""
    return _by_doc_type().get(doc_type)


def all_packs() -> list[RulePack]:
    return sorted(load_packs().values(), key=lambda pack: pack.id)


def reload() -> None:
    """Drop the cache. Used by tests; there is no hot-reload in production on purpose."""
    load_packs.cache_clear()
    _by_doc_type.cache_clear()
