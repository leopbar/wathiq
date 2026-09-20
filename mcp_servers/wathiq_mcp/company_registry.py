"""MCP server: company registry (SIMULATED).

What a real one would be: the government registry a bank queries to confirm that a trade
licence belongs to the company it names, and that the company is still trading.

What this is: an invented list of fifteen fake companies in `data.py`. It contacts nothing.
Every answer it returns carries `"simulated": true`, and the UI shows a SIMULATED badge next
to anything sourced from it — so a demo can never be mistaken for a real verification.

Read-only: there is no tool here that changes anything.
"""

from __future__ import annotations

from typing import Any

from wathiq_mcp.data import COMPANIES, normalise, similarity
from wathiq_mcp.runtime import build_server, serve

DEFAULT_PORT = 9102

server = build_server(
    name="wathiq-company-registry",
    title="Company registry (simulated)",
    instructions=(
        "Look up a company by licence number or by name. Results are from an invented "
        "registry of fake companies and must never be treated as a real verification."
    ),
)


def _public(company: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "license_number": company["license_number"],
        "registered_name": company["registered_name"],
        "legal_form": company["legal_form"],
        "status": company["status"],
        "activity": company["activity"],
        "authority": company["authority"],
        "established": company["established"],
        "simulated": True,
        "source": "Simulated company registry — invented data, no real registry contacted.",
        **extra,
    }


@server.tool(
    title="Look up a company by licence number",
    description=(
        "Returns the registered company for a trade licence number, or found=false if the "
        "registry has no such licence. Simulated data."
    ),
)
def lookup_by_license(license_number: str) -> dict[str, Any]:
    wanted = license_number.strip().upper().replace(" ", "")
    for company in COMPANIES:
        if company["license_number"].replace("-", "") == wanted.replace("-", ""):
            return {"found": True, "company": _public(company)}
    return {
        "found": False,
        "license_number": license_number,
        "simulated": True,
        "note": "No company in the simulated registry holds this licence number.",
    }


@server.tool(
    title="Search the registry by company name",
    description=(
        "Fuzzy name search. Returns the best matches with a similarity score, so a caller can "
        "tell an exact registration from a near miss. Simulated data."
    ),
)
def search_by_name(name: str, limit: int = 3) -> dict[str, Any]:
    scored: list[tuple[float, dict[str, Any], str]] = []
    for company in COMPANIES:
        candidates = [company["registered_name"], *company["aliases"]]
        best = max(candidates, key=lambda candidate: similarity(name, candidate))
        score = similarity(name, best)
        if score > 0:
            scored.append((score, company, best))

    scored.sort(key=lambda item: item[0], reverse=True)
    matches = [
        _public(
            company,
            match_score=score,
            matched_on=matched,
            exact=normalise(matched) == normalise(name),
        )
        for score, company, matched in scored[: max(1, min(limit, 10))]
    ]
    return {"query": name, "match_count": len(matches), "matches": matches, "simulated": True}


@server.tool(
    title="Check whether two names are the same company",
    description=(
        "Compares two spellings of a company name against the registry and says which one is "
        "the registered name. This is what resolves a trade licence / memorandum mismatch."
    ),
)
def reconcile_names(name_a: str, name_b: str) -> dict[str, Any]:
    best_match: dict[str, Any] | None = None
    best_score = 0.0
    for company in COMPANIES:
        candidates = [company["registered_name"], *company["aliases"]]
        score = max(
            min(similarity(name_a, candidate), similarity(name_b, candidate))
            for candidate in candidates
        )
        if score > best_score:
            best_score, best_match = score, company

    if best_match is None or best_score < 0.5:
        return {
            "same_company": False,
            "confidence": round(best_score, 3),
            "registered_name": None,
            "explanation": (
                "Neither spelling matches a company in the simulated registry closely enough "
                "to call them the same entity."
            ),
            "simulated": True,
        }

    return {
        "same_company": True,
        "confidence": round(best_score, 3),
        "registered_name": best_match["registered_name"],
        "license_number": best_match["license_number"],
        "status": best_match["status"],
        "explanation": (
            f"Both spellings resolve to {best_match['registered_name']!r} in the simulated "
            "registry, which is the registered spelling."
        ),
        "simulated": True,
    }


if __name__ == "__main__":  # pragma: no cover - container entry point
    serve(server, DEFAULT_PORT)
