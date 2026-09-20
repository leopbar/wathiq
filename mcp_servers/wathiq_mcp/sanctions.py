"""MCP server: sanctions screening (SIMULATED SAMPLE LIST).

What a real one would be: a screening service over official sanctions and PEP lists, with
fuzzy matching, transliteration handling and a case management workflow behind it.

What this is: five invented names in `data.py`. It is a sample, not a list. Nothing here is a
real sanctioned person or entity, and two of the entries are deliberately *close* to the demo
people so that a "possible match" — the thing a human must always decide — actually occurs in
a demo.

The important design point: this server never returns a verdict. It returns matches and
scores. Deciding what a possible match means is a mandatory human review, and the graph is
built so that it cannot be anything else.
"""

from __future__ import annotations

from typing import Any

from wathiq_mcp.data import SANCTIONS, similarity
from wathiq_mcp.runtime import build_server, serve

DEFAULT_PORT = 9103

# Above this, a name is close enough that a person must look at it.
POSSIBLE_MATCH = 0.5
# Above this, the two names are the same string in all but spelling.
STRONG_MATCH = 0.8

server = build_server(
    name="wathiq-sanctions",
    title="Sanctions screening (simulated sample list)",
    instructions=(
        "Screen a person or company name against a small invented sample list. Returns "
        "candidate matches and scores; it never returns a decision."
    ),
)


@server.tool(
    title="Screen a name against the sample list",
    description=(
        "Returns every entry whose name or alias is similar to the one given, with a score "
        "and a band (none / possible / strong). A possible match always needs a human."
    ),
)
def screen_name(name: str, entity_type: str = "person") -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for entry in SANCTIONS:
        candidates = [entry["name"], *entry["aliases"]]
        best = max(candidates, key=lambda candidate: similarity(name, candidate))
        score = similarity(name, best)
        if score >= POSSIBLE_MATCH:
            matches.append(
                {
                    "id": entry["id"],
                    "matched_name": best,
                    "list": entry["list"],
                    "country": entry["country"],
                    "reason": entry["reason"],
                    "score": score,
                    "band": "strong" if score >= STRONG_MATCH else "possible",
                }
            )

    matches.sort(key=lambda match: match["score"], reverse=True)
    band = matches[0]["band"] if matches else "none"
    return {
        "query": name,
        "entity_type": entity_type,
        "band": band,
        "match_count": len(matches),
        "matches": matches,
        "requires_human_decision": band != "none",
        "simulated": True,
        "source": (
            "SIMULATED. Five invented names — not a real sanctions source. A match here means "
            "nothing about the real person or company of that name."
        ),
    }


@server.tool(
    title="Describe the sample list",
    description=(
        "How many entries the sample list holds and what it is. Used by the About screen so "
        "the demo can state exactly what it screened against."
    ),
)
def describe_list() -> dict[str, Any]:
    return {
        "entry_count": len(SANCTIONS),
        "name": "Simulated sample list",
        "simulated": True,
        "note": (
            "Invented entries for demonstration. A production system would screen against "
            "official lists through a licensed provider."
        ),
        "thresholds": {"possible_match": POSSIBLE_MATCH, "strong_match": STRONG_MATCH},
    }


if __name__ == "__main__":  # pragma: no cover - container entry point
    serve(server, DEFAULT_PORT)
