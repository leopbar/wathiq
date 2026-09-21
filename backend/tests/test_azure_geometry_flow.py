"""The bounding box, end to end, without Azure.

This is the M6 claim that matters most on screen: a reviewer sees the value highlighted on the
page instead of hunting for it. Proving it needs the geometry to survive the whole journey —

    OCR backend → OcrResult.line_boxes → DocumentState (checkpointed) → the worker →
    geometry.locate → FieldState.bbox → the database → the API → DocumentViewer

— and every one of those is a place it could be dropped. `tests/test_azure.py` tests the pieces;
this tests that they are actually connected.

It runs offline by substituting an `OcrBackend` that returns geometry. That is the point of the
interface: a fake that reports boxes exercises exactly the code path Document Intelligence will,
so the wiring is proven without a key, a network or a bill. Only the *source* of the coordinates
is faked; every line they travel through is real.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.agent import ocr as ocr_module
from app.agent.ocr import LineBox, OcrBackend, OcrResult
from app.services.pdf import simple_pdf

SETTLED = {"completed", "rejected", "failed", "needs_review"}

LICENCE = [
    ("Licence number", "CN-9007777"),
    ("Company name (EN)", "Northwind Shipping LLC"),
    ("Licensing authority", "Department of Economic Development"),
    ("Business activity", "General trading"),
    ("Issue date", "2024-03-01"),
    ("Expiry date", "2030-03-01"),
]


class GeometryOcr(OcrBackend):
    """An OCR backend that reports geometry, the way Document Intelligence does.

    It reads the PDF with the demo reader and then attaches a plausible box and a per-line
    confidence to each line. The boxes are laid out down the page in reading order, which is
    what a real engine returns for a document laid out this way.
    """

    def __init__(self) -> None:
        self._demo = ocr_module.DemoOcr()

    def read(self, data: bytes, mime_type: str) -> OcrResult:
        base = self._demo.read(data, mime_type)
        boxes = [
            LineBox(
                text=line,
                page=1,
                # Stacked down the page: 4% tall, 3% apart, starting near the top.
                bbox=[0.12, round(0.08 + index * 0.05, 5), 0.55, 0.04],
                # One line deliberately reads badly, so the `read` signal has something to say.
                confidence=0.42 if line == "CN-9007777" else 0.97,
            )
            for index, line in enumerate(base.lines)
        ]
        return OcrResult(
            text=base.text,
            confidence=0.93,
            page_count=base.page_count,
            lines=base.lines,
            engine="fake-geometry-ocr",
            line_boxes=boxes,
        )

    @property
    def label(self) -> str:
        return "Fake OCR with geometry (test double for Document Intelligence)"


@pytest.fixture
def geometry_ocr(monkeypatch):
    """Swap the OCR backend for the run of one test, then put the real one back."""
    ocr_module.reset_ocr()
    monkeypatch.setattr(ocr_module, "_backend", GeometryOcr())
    yield
    ocr_module.reset_ocr()


async def _run_case(client: AsyncClient, headers: dict[str, str]) -> dict:
    created = await client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "case_type": "kyc_refresh",
            "customer_name": "Northwind Shipping LLC",
            "priority": "normal",
        },
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    pdf = simple_pdf("Trade Licence", LICENCE, "Synthetic")
    upload = await client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        files={"files": ("trade_licence.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    assert (await client.post(f"/api/v1/cases/{case_id}/start", headers=headers)).status_code == 200

    for _ in range(60):
        await asyncio.sleep(0.25)
        detail = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
        if detail["status"] in SETTLED:
            return detail
    pytest.fail(f"case {case_id} never settled; last status {detail['status']}")


async def test_geometry_from_the_ocr_reaches_the_field_the_api_returns(
    client: AsyncClient, auth, geometry_ocr
) -> None:
    """A box on the page becomes a box on the field, all the way out through the API."""
    headers = await auth("ops_officer")
    detail = await _run_case(client, headers)

    fields = {field["name"]: field for field in detail["fields"]}
    assert fields, "the pipeline produced no fields"

    licence = fields["license_number"]
    assert licence["value"] == "CN-9007777"

    # The claim: a real source region, in the normalised [x, y, w, h] the viewer draws.
    assert licence["bbox"] is not None, "the bounding box was dropped somewhere in the pipeline"
    x, y, w, h = licence["bbox"]
    assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
    assert 0.0 < w <= 1.0 and 0.0 < h <= 1.0
    assert licence["page"] == 1


async def test_the_sixth_signal_appears_only_because_the_engine_reported_one(
    client: AsyncClient, auth, geometry_ocr
) -> None:
    """`read` is present here and absent in demo mode, and it moves the score.

    The badly-read licence number was given 0.42 by the fake engine; every other line got 0.97.
    So the signal must exist, and it must be *lower* on that field than on its neighbours —
    which is the whole point of asking about the value rather than the page.
    """
    headers = await auth("ops_officer")
    detail = await _run_case(client, headers)
    fields = {field["name"]: field for field in detail["fields"]}

    def read_signal(name: str) -> dict | None:
        signals = fields[name].get("signals") or []
        return next((s for s in signals if s["key"] == "read"), None)

    smudged = read_signal("license_number")
    assert smudged is not None, "the read signal never reached the field"
    assert smudged["value"] == pytest.approx(0.42, abs=0.01)

    clean = read_signal("company_name_en")
    assert clean is not None
    assert clean["value"] > smudged["value"]


async def test_demo_mode_produces_no_box_and_no_read_signal(
    client: AsyncClient, auth
) -> None:
    """The control. Without an engine that reports geometry, nothing is invented.

    Run without the `geometry_ocr` fixture, so the real demo reader is used. This is what makes
    the two tests above meaningful: they show the geometry arriving *because* the engine
    supplied it, not because the pipeline manufactures it.
    """
    headers = await auth("ops_officer")
    detail = await _run_case(client, headers)
    fields = {field["name"]: field for field in detail["fields"]}

    licence = fields["license_number"]
    assert licence["value"] == "CN-9007777"
    assert licence["bbox"] is None, "a box appeared with no engine to have measured it"

    signals = {s["key"] for s in (licence.get("signals") or [])}
    assert "read" not in signals
    # The other five are all still there, so the field is scored exactly as it was before M6.
    assert {"ocr", "grounded", "label", "shape"} <= signals
