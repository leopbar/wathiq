"""Tests for the AI reasoning layer.

These are deliberately offline and deterministic: the demo OCR, classifier, extractor and rule
engine take no network call, so the same input always gives the same answer. That is what lets
the Quality Lab (M5) treat them as a baseline.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent import rules as rule_engine
from app.agent.classifier import classify
from app.agent.extractor import DemoExtractor, parse_date
from app.agent.graph import build_graph, mermaid
from app.agent.ocr import DemoOcr
from app.db.enums import DocTypeKey
from app.services.pdf import simple_pdf

TRADE_LICENCE_FIELDS = [
    ("Licence number", "CN-1234567"),
    ("Company name (EN)", "Al Noor Trading LLC"),
    ("Licensing authority", "Department of Economic Development"),
    ("Business activity", "General trading"),
    ("Issue date", "2024-03-15"),
    ("Expiry date", "2027-03-15"),
]

SCHEMA = [
    {"name": "license_number", "label_en": "Licence number", "is_critical": True},
    {"name": "company_name_en", "label_en": "Company name (EN)", "is_critical": True},
    {"name": "licensing_authority", "label_en": "Licensing authority"},
    {"name": "business_activity", "label_en": "Business activity"},
    {"name": "issue_date", "label_en": "Issue date"},
    {"name": "expiry_date", "label_en": "Expiry date", "is_critical": True},
]


def _licence_pdf(fields: list[tuple[str, str]] | None = None) -> bytes:
    return simple_pdf("Trade Licence", fields or TRADE_LICENCE_FIELDS, "Synthetic demo document")


# ------------------------------------------------------------------------------ ocr


def test_demo_ocr_reads_back_what_the_pdf_writer_wrote() -> None:
    result = DemoOcr().read(_licence_pdf(), "application/pdf")
    assert result.confidence > 0.9
    assert "CN-1234567" in result.text
    assert "Al Noor Trading LLC" in result.text
    assert result.page_count == 1


def test_demo_ocr_is_honest_about_images() -> None:
    """An image needs real OCR. The demo backend must say it cannot, not invent text."""
    result = DemoOcr().read(b"\x89PNG\r\n\x1a\n", "image/png")
    assert result.text == ""
    assert result.confidence == 0.0
    assert result.engine == "demo-unsupported"


def test_demo_ocr_reports_a_pdf_with_no_text_layer() -> None:
    result = DemoOcr().read(b"%PDF-1.4\n%%EOF\n", "application/pdf")
    assert result.text == ""
    assert result.engine == "demo-no-text-layer"


# ------------------------------------------------------------------------- classify


def test_classifier_identifies_a_trade_licence() -> None:
    text = DemoOcr().read(_licence_pdf(), "application/pdf").text
    doc_type, confidence, evidence = classify(text, "licence.pdf")
    assert doc_type is DocTypeKey.trade_license
    assert confidence > 0.5
    assert evidence  # the reason for the decision is recorded, not just the answer


def test_classifier_refuses_to_guess_on_an_unknown_document() -> None:
    doc_type, confidence, _ = classify("A letter about nothing in particular.", "note.pdf")
    assert doc_type is DocTypeKey.unknown
    assert confidence < 0.5


# --- Arabic: the first real Arabic licence put through this system scored zero, because every
# --- keyword was English and the filename was camel-cased. Both are covered here.

ARABIC_LICENCE = """رخصة تجارية
دائرة التنمية الاقتصادية
رقم الرخصة: CN-1042288
الشكل القانوني: ذ.م.م"""


def test_classifier_identifies_an_arabic_trade_licence() -> None:
    doc_type, confidence, evidence = classify(ARABIC_LICENCE, "scan.jpg")
    assert doc_type is DocTypeKey.trade_license
    assert confidence > 0.5
    assert evidence


def test_arabic_spelling_variants_still_match() -> None:
    """Vowel marks, a stretched letter and a different alef are the same word to a reader."""
    stretched = ARABIC_LICENCE.replace(
        "\u0631\u062e\u0635\u0629", "\u0631\u062e\u0640\u0640\u0635\u0629"
    )
    marked = stretched.replace("\u062a\u062c\u0627\u0631\u064a\u0629",
                               "\u062a\u0650\u062c\u0627\u0631\u064a\u0629")
    doc_type, _, _ = classify(marked, "scan.jpg")
    assert doc_type is DocTypeKey.trade_license


def test_an_arabic_salary_certificate_is_recognised() -> None:
    text = (
        "\u0634\u0647\u0627\u062f\u0629 \u0631\u0627\u062a\u0628\n"
        "\u0627\u0633\u0645 \u0627\u0644\u0645\u0648\u0638\u0641: "
        "\u0645\u0631\u064a\u0645\n"
        "\u0627\u0644\u0631\u0627\u062a\u0628 \u0627\u0644\u0623\u0633\u0627"
        "\u0633\u064a: 18000"
    )
    doc_type, _, _ = classify(text, "doc.pdf")
    assert doc_type is DocTypeKey.salary_certificate


def test_a_camel_cased_filename_is_evidence() -> None:
    """`tradeLicenseFake.jpg` used to score nothing: its words were never separated."""
    doc_type, _, evidence = classify("licence number CN-1042288", "tradeLicenseFake.jpg")
    assert doc_type is DocTypeKey.trade_license
    assert "trade license" in evidence


def test_an_english_document_is_unaffected_by_the_arabic_keywords() -> None:
    text = DemoOcr().read(_licence_pdf(), "application/pdf").text
    assert classify(text, "licence.pdf")[:2] == classify(text, "licence.pdf")[:2]
    assert classify(text, "licence.pdf")[0] is DocTypeKey.trade_license


def test_arabic_prose_that_is_not_a_known_document_is_still_refused() -> None:
    """The Arabic keywords must not turn every Arabic page into a trade licence."""
    text = (
        "\u0647\u0630\u0647 \u0631\u0633\u0627\u0644\u0629 \u0639\u0627\u062f"
        "\u064a\u0629 \u0644\u0627 \u062a\u062e\u0635 \u0623\u064a \u0645\u0633"
        "\u062a\u0646\u062f \u0631\u0633\u0645\u064a"
    )
    doc_type, confidence, _ = classify(text, "note.pdf")
    assert doc_type is DocTypeKey.unknown
    assert confidence < 0.5


# -------------------------------------------------------------------------- extract


def test_extractor_reads_the_values_next_to_the_labels() -> None:
    lines = DemoOcr().read(_licence_pdf(), "application/pdf").lines
    found = DemoExtractor().extract(lines, SCHEMA, "trade_license")
    assert found["license_number"].value == "CN-1234567"
    assert found["company_name_en"].value == "Al Noor Trading LLC"
    assert found["expiry_date"].value == "2027-03-15"
    assert found["license_number"].confidence > 0.8


def test_extractor_never_invents_a_value_it_cannot_see() -> None:
    lines = ["LICENCE NUMBER", "CN-1234567"]
    found = DemoExtractor().extract(lines, SCHEMA, "trade_license")
    assert "company_name_en" not in found  # absent, rather than guessed


def test_low_quality_text_scores_lower_confidence() -> None:
    clean = DemoExtractor().extract(["LICENCE NUMBER", "CN-1234567"], SCHEMA, "trade_license")
    noisy = DemoExtractor().extract(["LICENCE NUMBER", "CN-1?3�567"], SCHEMA, "trade_license")
    assert noisy["license_number"].confidence < clean["license_number"].confidence


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2027-03-15", date(2027, 3, 15)),
        ("15/03/2027", date(2027, 3, 15)),
        # A real UAE licence writes the year first with slashes. This shape was read as no date
        # at all, so the expiry rules never ran on it.
        ("2024/06/15", date(2024, 6, 15)),
        ("2026.06.14", date(2026, 6, 14)),
        ("15-03-2027", date(2027, 3, 15)),
        ("1/3/2027", date(2027, 3, 1)),
        ("Issue date: 2024/06/15 (Gregorian)", date(2024, 6, 15)),
        ("nope", None),
        # An impossible date is not a date: 31 February must not become 3 March.
        ("2027-02-31", None),
        ("2027/13/01", None),
    ],
)
def test_parse_date(text: str, expected: date | None) -> None:
    assert parse_date(text) == expected


# ---------------------------------------------------------------------------- rules


def test_expired_document_fails_its_rule() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    outcomes = rule_engine.evaluate(
        [
            {
                "id": "TL_NOT_EXPIRED",
                "expr": "expiry_date > today",
                "severity": "critical",
                "message": "Trade licence is expired",
            }
        ],
        {"trade_license": {"expiry_date": yesterday}},
        "trade_license",
    )
    assert outcomes[0].passed is False
    assert outcomes[0].severity == "critical"


def test_valid_document_passes_its_rule() -> None:
    future = (date.today() + timedelta(days=400)).isoformat()
    outcomes = rule_engine.evaluate(
        [{"id": "TL_NOT_EXPIRED", "expr": "expiry_date > today", "severity": "critical"}],
        {"trade_license": {"expiry_date": future}},
        "trade_license",
    )
    assert outcomes[0].passed is True


def test_cross_document_name_match_tolerates_punctuation() -> None:
    outcomes = rule_engine.evaluate(
        [
            {
                "id": "TL_NAME_MATCHES_MOA",
                "expr": "trade_license.company_name_en ~= moa.company_name_en",
                "severity": "warning",
            }
        ],
        {
            "trade_license": {"company_name_en": "Al Noor Trading LLC"},
            "moa": {"company_name_en": "Al Noor Trading L.L.C."},
        },
        "trade_license",
    )
    assert outcomes[0].passed is True


def test_cross_document_mismatch_is_caught() -> None:
    outcomes = rule_engine.evaluate(
        [
            {
                "id": "TL_NAME_MATCHES_MOA",
                "expr": "trade_license.company_name_en ~= moa.company_name_en",
                "severity": "warning",
            }
        ],
        {
            "trade_license": {"company_name_en": "Al Noor Trading LLC"},
            "moa": {"company_name_en": "Gulf Horizon Contracting"},
        },
        "trade_license",
    )
    assert outcomes[0].passed is False


def test_a_rule_we_cannot_evaluate_is_reported_not_silently_passed() -> None:
    outcomes = rule_engine.evaluate(
        [{"id": "WEIRD", "expr": "something we do not support", "severity": "warning"}],
        {"trade_license": {}},
        "trade_license",
    )
    # `passed` is True only because there is nothing to fail; `evaluated` is the flag that
    # says the rule never ran, and callers must read that one.
    assert outcomes[0].evaluated is False
    assert "not evaluated" in outcomes[0].detail


# ---------------------------------------------------------------------------- graph


def test_graph_has_the_nodes_and_the_branch() -> None:
    graph = build_graph()
    assert set(graph.nodes) == {
        "ocr",
        "guardrails",
        "supervisor",
        "extract_worker",
        "critic",
        "investigator",
        "validate",
        "review_gate",
        "finalize",
    }


def test_published_diagram_matches_the_real_node_names() -> None:
    """The About screen must not show a graph we are not running."""
    drawing = mermaid()
    for node in build_graph().nodes:
        assert node in drawing


async def test_review_gate_pauses_and_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The heart of human-in-the-loop: the graph stops, waits, and carries on with the answer.

    The nodes are stubbed so this test covers the graph's control flow and the interrupt, not
    the database.
    """
    from app.agent import nodes

    async def noop_emit(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(nodes, "_emit", noop_emit)

    graph = build_graph().compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test-thread-1"}}
    state = {
        "case_id": "11111111-1111-1111-1111-111111111111",
        "thread_id": "test-thread-1",
        "case_type": "kyc_refresh",
        "documents": [],
        "fields": [],
        "findings": [],
        # A reason is present, so `validate` must route into the review gate.
        "review_reasons": [{"code": "DOCUMENT_EXPIRED", "label": "Trade licence is expired"}],
    }

    result = await graph.ainvoke(state, config=config)
    assert "__interrupt__" in result, "the graph should have paused at the review gate"

    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("review_gate",)

    resumed = await graph.ainvoke(
        Command(resume={"decision": "approve", "corrections": {}}), config=config
    )
    assert resumed["decision"] == "approve"
    assert resumed["needs_review"] is False


async def test_confident_case_skips_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """With nothing to review, the case goes straight through — no human, no waiting."""
    from app.agent import nodes

    async def noop_emit(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(nodes, "_emit", noop_emit)

    graph = build_graph().compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test-thread-2"}}
    result = await graph.ainvoke(
        {
            "case_id": "22222222-2222-2222-2222-222222222222",
            "thread_id": "test-thread-2",
            "case_type": "kyc_refresh",
            "documents": [],
            "fields": [],
            "findings": [],
            "review_reasons": [],
        },
        config=config,
    )
    assert "__interrupt__" not in result
    assert result["straight_through"] is True
