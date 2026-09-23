"""MCP server: core banking (SIMULATED — the only server that can write).

What a real one would be: the bank's system of record. Posting a KYC refresh to it changes a
company's file; posting an income verification (use case 2) records a verified salary on a
person's file for a loan decision.

What this is: an in-memory stand-in. It accepts posts, stores them in a dictionary and hands
back a reference number. Nothing leaves this container.

Two rules are enforced here, and they are the reason this server exists as its own process:

1. **Write only after approval.** Both posting tools refuse unless it is told who approved
   the case and under what authority. `approval_kind="human"` means a named person decided;
   `approval_kind="straight_through_policy"` means a written policy pre-authorised it because
   nothing needed a person. Both are accepted, and the difference is stored — so a record
   never says a human approved something no human saw.
2. **Idempotency.** Every post carries an idempotency key. Posting the same key twice returns
   the first reference and reports `duplicate: true` instead of writing again. That is what
   makes a retry — after a crash, a timeout or a Conductor redelivery — safe.

Least privilege: this server's address is given only to the node that posts. The investigator,
which reads freely from the registry and the sanctions list, is never given it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from wathiq_mcp.data import CUSTOMERS, similarity
from wathiq_mcp.runtime import build_server, serve

DEFAULT_PORT = 9104

server = build_server(
    name="wathiq-core-banking",
    title="Core banking (simulated)",
    instructions=(
        "Read a simulated customer record and post an approved KYC refresh or income "
        "verification against it. Posting requires an approval and an idempotency key. Nothing "
        "here touches a real system."
    ),
)

# The authorities this system of record accepts. Anything else is refused: a made-up kind
# would let a caller invent an approval that no policy covers.
APPROVAL_KINDS = ("human", "straight_through_policy")

# reference number → what was posted. In-memory: restarting the container forgets everything,
# which is correct for a simulator and keeps the demo reproducible.
_POSTINGS: dict[str, dict[str, Any]] = {}
# idempotency key → reference number.
_KEYS: dict[str, str] = {}


# What each posting tool writes, the reference prefix it issues, the customer segment it may
# write to, and the fields without which the record would mean nothing.
RECORDS: dict[str, dict[str, Any]] = {
    "kyc_refresh": {"prefix": "SIM-KYC", "segments": ("Corporate", "SME"), "requires": ()},
    "income_verification": {
        "prefix": "SIM-INC",
        "segments": ("Retail",),
        "requires": ("employer_name", "total_salary"),
    },
}


def _reference(idempotency_key: str, prefix: str = "SIM-KYC") -> str:
    """A stable, readable reference derived from the key, so retries are obviously the same."""
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def _customer(customer_id: str) -> dict[str, Any] | None:
    return next((c for c in CUSTOMERS if c["customer_id"] == customer_id.strip()), None)


@server.tool(
    title="Read a simulated customer record",
    description="Find a customer by id or by name. Read-only. Simulated data.",
)
def get_customer(customer_id: str = "", name: str = "") -> dict[str, Any]:
    if customer_id:
        for customer in CUSTOMERS:
            if customer["customer_id"] == customer_id.strip():
                return {"found": True, "customer": {**customer, "simulated": True}}
    if name:
        best = max(CUSTOMERS, key=lambda customer: similarity(name, customer["name"]))
        if similarity(name, best["name"]) >= 0.6:
            return {
                "found": True,
                "customer": {**best, "simulated": True},
                "match_score": similarity(name, best["name"]),
            }
    return {
        "found": False,
        "simulated": True,
        "note": "No customer in the simulated core banking stand-in matches.",
    }


@server.tool(
    title="Post an approved KYC refresh",
    description=(
        "Writes a KYC refresh against a simulated customer. Refuses unless an approver is "
        "named and the kind of approval is one this system accepts ('human' or "
        "'straight_through_policy'). Repeating the same idempotency key returns the original "
        "reference instead of writing twice."
    ),
)
def post_kyc_refresh(
    case_id: str,
    customer_id: str,
    idempotency_key: str,
    approved_by: str,
    approval_kind: str = "human",
    approved_at: str = "",
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _post(
        "kyc_refresh",
        case_id=case_id,
        customer_id=customer_id,
        idempotency_key=idempotency_key,
        approved_by=approved_by,
        approval_kind=approval_kind,
        approved_at=approved_at,
        fields=fields,
    )


@server.tool(
    title="Post an approved income verification",
    description=(
        "Added for salary certificates. Records a verified salary on a simulated individual's "
        "file for a loan decision. Same approval and idempotency rules as a KYC refresh; also "
        "refuses a company's file and an income record with no employer or total salary."
    ),
)
def post_income_verification(
    case_id: str,
    customer_id: str,
    idempotency_key: str,
    approved_by: str,
    approval_kind: str = "human",
    approved_at: str = "",
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _post(
        "income_verification",
        case_id=case_id,
        customer_id=customer_id,
        idempotency_key=idempotency_key,
        approved_by=approved_by,
        approval_kind=approval_kind,
        approved_at=approved_at,
        fields=fields,
    )


def _post(
    record_kind: str,
    *,
    case_id: str,
    customer_id: str,
    idempotency_key: str,
    approved_by: str,
    approval_kind: str,
    approved_at: str,
    fields: dict[str, Any] | None,
) -> dict[str, Any]:
    spec = RECORDS[record_kind]
    if not idempotency_key.strip():
        return {
            "posted": False,
            "error": "idempotency_key is required",
            "explanation": (
                "Without a key a retry after a timeout would post the same refresh twice."
            ),
        }
    if not approved_by.strip():
        return {
            "posted": False,
            "error": "approved_by is required",
            "explanation": (
                "This system of record only accepts a refresh with a named approver — a "
                "person, or the policy that stood in for one."
            ),
        }
    if approval_kind not in APPROVAL_KINDS:
        return {
            "posted": False,
            "error": f"approval_kind must be one of {', '.join(APPROVAL_KINDS)}",
            "explanation": (
                "The authority behind a posting is part of the record. An unrecognised one "
                "would hide whether a person or a policy allowed it."
            ),
        }

    existing = _KEYS.get(idempotency_key)
    if existing is not None:
        return {
            "posted": True,
            "duplicate": True,
            "reference": existing,
            "posted_at": _POSTINGS[existing]["posted_at"],
            "simulated": True,
            "explanation": (
                "This idempotency key was already used. The original reference is returned and "
                "nothing was written again."
            ),
        }

    customer = _customer(customer_id)
    if customer is not None and customer["segment"] not in spec["segments"]:
        return {
            "posted": False,
            "error": (
                f"a {record_kind.replace('_', ' ')} cannot be written to a "
                f"{customer['segment']} customer"
            ),
            "explanation": (
                "Each record belongs on one kind of file. An income verification on a "
                "company's file, or a company KYC refresh on a person's, would be wrong data "
                "in the system of record."
            ),
        }
    missing = [name for name in spec["requires"] if not (fields or {}).get(name)]
    if missing:
        return {
            "posted": False,
            "error": f"missing required field(s): {', '.join(missing)}",
            "explanation": "The record would not say what it is evidence of.",
        }

    reference = _reference(idempotency_key, spec["prefix"])
    record = {
        "reference": reference,
        "record_kind": record_kind,
        "case_id": case_id,
        "customer_id": customer_id,
        "approved_by": approved_by,
        "approval_kind": approval_kind,
        "approved_at": approved_at or datetime.now(UTC).isoformat(),
        "posted_at": datetime.now(UTC).isoformat(),
        "field_count": len(fields or {}),
        "simulated": True,
    }
    _POSTINGS[reference] = record
    _KEYS[idempotency_key] = reference
    return {"posted": True, "duplicate": False, **record}


@server.tool(
    title="Read a posting back",
    description="Returns a posting by reference, so a caller can confirm what was written.",
)
def get_posting(reference: str) -> dict[str, Any]:
    record = _POSTINGS.get(reference.strip())
    if record is None:
        return {"found": False, "reference": reference, "simulated": True}
    return {"found": True, "posting": record}


if __name__ == "__main__":  # pragma: no cover - container entry point
    serve(server, DEFAULT_PORT)
