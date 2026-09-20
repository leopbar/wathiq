"""End-to-end tests of the pipeline through the API.

These go through the real HTTP endpoints, the real graph and the real PostgreSQL checkpointer.
They are the tests that would catch the pipeline being wired up wrongly, which unit tests on
the individual nodes cannot.

The pipeline runs as a background task, so each test waits for the case to settle instead of
assuming the work is done when the request returns.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.services.pdf import simple_pdf

SETTLED = {"completed", "rejected", "failed", "needs_review"}

VALID_LICENCE = [
    ("Licence number", "CN-9001234"),
    ("Company name (EN)", "Bright Sands Logistics LLC"),
    ("Licensing authority", "Department of Economic Development"),
    ("Business activity", "Freight forwarding"),
    ("Issue date", "2024-01-10"),
    ("Expiry date", "2030-01-10"),
]

EXPIRED_LICENCE = [
    ("Licence number", "CN-9005678"),
    ("Company name (EN)", "Old Harbour Trading LLC"),
    ("Licensing authority", "Department of Economic Development"),
    ("Business activity", "General trading"),
    ("Issue date", "2018-02-01"),
    ("Expiry date", "2020-02-01"),
]


async def _wait_for_settled(client: AsyncClient, headers: dict[str, str], case_id: str) -> dict:
    """Poll until the pipeline stops moving. Fails loudly rather than hanging forever."""
    for _ in range(60):
        await asyncio.sleep(0.25)
        detail = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
        if detail["status"] in SETTLED:
            return detail
    pytest.fail(f"case {case_id} never settled; last status {detail['status']}")


async def _run_case(
    client: AsyncClient, headers: dict[str, str], rows: list[tuple[str, str]], customer: str
) -> dict:
    created = await client.post(
        "/api/v1/cases",
        headers=headers,
        json={"case_type": "kyc_refresh", "customer_name": customer, "priority": "normal"},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    pdf = simple_pdf("Trade Licence", rows, "Synthetic")
    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        files={"files": ("trade_licence.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text

    started = await client.post(f"/api/v1/cases/{case_id}/start", headers=headers)
    assert started.status_code == 200, started.text
    assert started.json()["thread_id"]

    return await _wait_for_settled(client, headers, case_id)


async def test_a_clean_document_goes_straight_through(client: AsyncClient, auth) -> None:
    """Nothing wrong with it, so no human is asked and the case completes on its own."""
    headers = await auth("ops_officer")
    detail = await _run_case(client, headers, VALID_LICENCE, "Bright Sands Logistics LLC")

    assert detail["status"] == "completed"
    assert detail["straight_through"] is True
    assert detail["confidence"] > 0.8
    assert detail["findings"] == []

    values = {f["name"]: f["value"] for f in detail["fields"]}
    assert values["license_number"] == "CN-9001234"
    assert values["company_name_en"] == "Bright Sands Logistics LLC"
    assert values["expiry_date"] == "2030-01-10"


async def test_the_document_is_classified_and_its_text_is_read(
    client: AsyncClient, auth
) -> None:
    headers = await auth("ops_officer")
    detail = await _run_case(client, headers, VALID_LICENCE, "Bright Sands Logistics LLC")

    document = detail["documents"][0]
    assert document["doc_type"] == "trade_license"
    assert document["classification_confidence"] > 0.5
    assert document["ocr_confidence"] > 0.9
    assert document["status"] == "extracted"


async def test_an_expired_licence_stops_for_a_human(client: AsyncClient, auth) -> None:
    """The rule fires, the graph interrupts, and a review task appears in the queue."""
    headers = await auth("ops_officer")
    detail = await _run_case(client, headers, EXPIRED_LICENCE, "Old Harbour Trading LLC")

    assert detail["status"] == "needs_review"
    codes = {f["code"] for f in detail["findings"]}
    assert "TL_NOT_EXPIRED" in codes

    reviewer = await auth("reviewer")
    queue = (
        await client.get(
            "/api/v1/review/queue", headers=reviewer, params={"page": 1, "size": 100}
        )
    ).json()
    tasks = [t for t in queue["items"] if t["case_id"] == detail["id"]]
    assert tasks, "the paused case should have produced a review task"
    assert tasks[0]["reason_code"] == "DOCUMENT_EXPIRED"


async def test_approval_resumes_the_graph_from_its_checkpoint(
    client: AsyncClient, auth
) -> None:
    """The heart of human-in-the-loop, through the real API and the real checkpointer."""
    headers = await auth("ops_officer")
    paused = await _run_case(client, headers, EXPIRED_LICENCE, "Old Harbour Trading LLC")
    assert paused["status"] == "needs_review"

    reviewer = await auth("reviewer")
    queue = (
        await client.get(
            "/api/v1/review/queue", headers=reviewer, params={"page": 1, "size": 100}
        )
    ).json()
    task = next(t for t in queue["items"] if t["case_id"] == paused["id"])

    await client.post(f"/api/v1/review/tasks/{task['id']}/claim", headers=reviewer)
    decision = await client.post(
        f"/api/v1/review/tasks/{task['id']}/decision",
        headers=reviewer,
        json={"decision": "approve", "reason_code": "FINDING_WAIVED", "note": "checked"},
    )
    assert decision.status_code == 200, decision.text

    detail = await _wait_for_settled(client, reviewer, paused["id"])
    assert detail["status"] == "completed"
    # It needed a person, so it is explicitly not straight-through.
    assert detail["straight_through"] is False


async def test_a_reviewers_resolution_survives_the_graph_resuming(
    client: AsyncClient, auth
) -> None:
    """Regression: the rules re-run on resume and used to recreate findings as `open`,
    silently undoing the reviewer's decision."""
    headers = await auth("ops_officer")
    paused = await _run_case(client, headers, EXPIRED_LICENCE, "Old Harbour Trading LLC")

    reviewer = await auth("reviewer")
    queue = (
        await client.get(
            "/api/v1/review/queue", headers=reviewer, params={"page": 1, "size": 100}
        )
    ).json()
    task = next(t for t in queue["items"] if t["case_id"] == paused["id"])
    await client.post(f"/api/v1/review/tasks/{task['id']}/claim", headers=reviewer)
    await client.post(
        f"/api/v1/review/tasks/{task['id']}/decision",
        headers=reviewer,
        json={"decision": "approve", "reason_code": "FINDING_WAIVED"},
    )

    detail = await _wait_for_settled(client, reviewer, paused["id"])
    statuses = {f["code"]: f["status"] for f in detail["findings"]}
    assert statuses["TL_NOT_EXPIRED"] == "resolved"


async def test_a_correction_is_applied_to_the_field(client: AsyncClient, auth) -> None:
    """A corrected value replaces the extracted one and is marked as corrected."""
    headers = await auth("ops_officer")
    paused = await _run_case(client, headers, EXPIRED_LICENCE, "Old Harbour Trading LLC")

    reviewer = await auth("reviewer")
    queue = (
        await client.get(
            "/api/v1/review/queue", headers=reviewer, params={"page": 1, "size": 100}
        )
    ).json()
    task = next(t for t in queue["items"] if t["case_id"] == paused["id"])
    await client.post(f"/api/v1/review/tasks/{task['id']}/claim", headers=reviewer)

    target = next(f for f in paused["fields"] if f["name"] == "company_name_en")
    await client.post(
        f"/api/v1/review/tasks/{task['id']}/decision",
        headers=reviewer,
        json={
            "decision": "correct",
            "reason_code": "OCR_ERROR",
            "field_corrections": [
                {"field_id": target["id"], "value": "Old Harbour Trading L.L.C."}
            ],
        },
    )

    detail = await _wait_for_settled(client, reviewer, paused["id"])
    corrected = next(f for f in detail["fields"] if f["name"] == "company_name_en")
    assert corrected["corrected_value"] == "Old Harbour Trading L.L.C."
    assert corrected["status"] == "corrected"


async def test_the_timeline_records_every_pipeline_step(client: AsyncClient, auth) -> None:
    """The audit trail must show the whole run, not just the outcome."""
    headers = await auth("ops_officer")
    detail = await _run_case(client, headers, VALID_LICENCE, "Bright Sands Logistics LLC")

    actions = [event["action"] for event in detail["timeline"]]
    for expected in (
        "case.created",
        "documents.uploaded",
        "case.started",
        "agent.ocr",
        "agent.classify.done",
        "agent.extract.done",
        "agent.validate",
        "agent.finalize",
        "pipeline.completed",
    ):
        assert expected in actions, f"{expected} missing from the timeline: {actions}"

