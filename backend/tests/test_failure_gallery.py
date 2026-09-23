"""The failure-mode gallery may only promise what the system does.

Every runnable scenario is sent through the real intake and the real pipeline, and must end in
the state it promises, showing the codes it says a reviewer will see. Every scenario proven by
tests must name tests that exist. If either drifts, the gallery would be describing a system
we do not have — and this file fails.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services import failure_gallery

SETTLED = {"completed", "rejected", "failed", "needs_review"}
TESTS_ROOT = Path(__file__).parent

RUNNABLE = [s for s in failure_gallery.scenarios() if s.runnable]
PROVEN = [s for s in failure_gallery.scenarios() if not s.runnable]


def test_ids_are_unique_and_every_entry_is_one_kind_or_the_other() -> None:
    ids = [s.id for s in failure_gallery.scenarios()]
    assert len(ids) == len(set(ids))
    for scenario in failure_gallery.scenarios():
        assert scenario.runnable != bool(scenario.evidence), scenario.id


def test_every_entry_is_explained_in_both_languages() -> None:
    for s in failure_gallery.scenarios():
        for text in (s.title_ar, s.problem_ar, s.detection_ar, s.outcome_ar, s.where_to_look_ar):
            assert text and any("؀" <= ch <= "ۿ" for ch in text), s.id


def _test_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    names.add(f"{node.name}::{item.name}")
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
    return names


@pytest.mark.parametrize("scenario", PROVEN, ids=lambda s: s.id)
def test_every_named_backend_test_exists(scenario: failure_gallery.Scenario) -> None:
    """Backend references are checked here. MCP-suite references live in another image and
    are checked by that suite's own run; they must at least be well-formed."""
    for reference in scenario.evidence:
        path, _, name = reference.partition("::")
        assert path.endswith(".py") and name, reference
        if not path.startswith("backend/tests/"):
            assert path.startswith("mcp_servers/tests/"), reference
            continue
        assert name in _test_names(TESTS_ROOT / Path(path).name), reference


async def _run(client: AsyncClient, headers: dict[str, str], scenario) -> dict:
    created = await client.post(
        "/api/v1/cases",
        headers=headers,
        json={"case_type": scenario.case_type, "customer_name": scenario.customer_name},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    files = []
    for index, item in enumerate(scenario.files):
        download = await client.get(
            f"/api/v1/failure-gallery/{scenario.id}/files/{index}", headers=headers
        )
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF")
        files.append(("files", (item.filename, download.content, "application/pdf")))

    upload = await client.post(f"/api/v1/cases/{case_id}/documents", headers=headers, files=files)
    assert upload.status_code == 201, upload.text
    started = await client.post(f"/api/v1/cases/{case_id}/start", headers=headers)
    assert started.status_code == 200, started.text

    for _ in range(120):
        await asyncio.sleep(0.25)
        detail = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
        if detail["status"] in SETTLED:
            return detail
    pytest.fail(f"{scenario.id}: case never settled; last status {detail['status']}")


@pytest.mark.parametrize("scenario", RUNNABLE, ids=lambda s: s.id)
async def test_every_runnable_scenario_does_what_it_promises(
    client: AsyncClient, auth, scenario: failure_gallery.Scenario
) -> None:
    detail = await _run(client, await auth("ops_officer"), scenario)

    assert detail["status"] == scenario.expected_status, (scenario.id, detail["status"])
    assert detail["straight_through"] is False, "a failure must never pass unseen"
    shown = {f["code"] for f in detail["findings"]} | {
        t.get("reason_code") for t in detail.get("review_tasks", [])
    }
    if scenario.expected_codes:
        assert shown & set(scenario.expected_codes), (scenario.id, sorted(c for c in shown if c))
    else:
        # The abstention scenarios: the classifier must refuse to name a type.
        assert any(d["doc_type"] == "unknown" for d in detail["documents"]), scenario.id


async def test_the_catalogue_needs_a_signed_in_user(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/failure-gallery")).status_code == 401


async def test_an_unknown_document_is_a_404(client: AsyncClient, auth) -> None:
    headers = await auth("ops_officer")
    response = await client.get("/api/v1/failure-gallery/nope/files/0", headers=headers)
    assert response.status_code == 404
