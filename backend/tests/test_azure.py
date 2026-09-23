"""M6: the Azure adapters, tested without Azure.

Every test here runs offline. That is not a limitation of the tests — it is the property being
tested. The whole design rests on three claims, and each one is checked below rather than
asserted in a document:

1. **Demo mode never loads an Azure SDK.** If it did, `WATHIQ_MODE=demo` would stop working on
   a machine without the extra installed, and the offline promise M1 made would be broken.
2. **A service is on only when its own endpoint is set.** Not "the mode is azure", which would
   make a half-configured deployment fail in a confusing place.
3. **Nothing is invented.** No highlight box without geometry, no confidence without a
   measurement, no value that is not in the document.

The pieces that genuinely need a network — a real model call, a real OCR read — are covered by
`pytest -m azure`, which is skipped unless the endpoints are configured. What is here is
everything that can be established without spending money.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agent import confidence, geometry
from app.agent import schema as extraction_schema
from app.agent.ocr import DemoOcr, LineBox, OcrResult

# --------------------------------------------------------------------- geometry


def _boxes() -> list[dict[str, object]]:
    """A page laid out the way the synthetic documents print: LABEL, then value."""
    return [
        {"text": "TRADE LICENCE", "page": 1, "bbox": [0.1, 0.05, 0.3, 0.03], "confidence": 0.99},
        {"text": "Licence number", "page": 1, "bbox": [0.1, 0.2, 0.2, 0.02], "confidence": 0.98},
        {"text": "CN-1234567", "page": 1, "bbox": [0.1, 0.24, 0.18, 0.02], "confidence": 0.94},
        {"text": "Company name", "page": 1, "bbox": [0.1, 0.3, 0.2, 0.02], "confidence": 0.97},
        {"text": "Al Noor Trading", "page": 1, "bbox": [0.1, 0.34, 0.25, 0.02], "confidence": 0.91},
        {"text": "LLC", "page": 1, "bbox": [0.1, 0.37, 0.06, 0.02], "confidence": 0.88},
        {"text": "Issued on 2024-01-15", "page": 2,
         "bbox": [0.1, 0.5, 0.3, 0.02], "confidence": 0.8},
    ]


def test_locate_finds_a_value_printed_on_its_own_line():
    bbox, page = geometry.locate("CN-1234567", _boxes())
    assert bbox == [0.1, 0.24, 0.18, 0.02]
    assert page == 1


def test_locate_finds_a_value_printed_inline_after_other_words():
    bbox, page = geometry.locate("2024-01-15", _boxes())
    assert bbox == [0.1, 0.5, 0.3, 0.02]
    assert page == 2


def test_locate_unions_a_value_wrapped_across_two_lines():
    """A long company name split by the OCR gets one box covering both fragments."""
    bbox, page = geometry.locate("Al Noor Trading LLC", _boxes())
    assert page == 1
    assert bbox is not None
    # Spans from the top of "Al Noor Trading" to the bottom of "LLC".
    assert bbox[1] == pytest.approx(0.34)
    assert bbox[1] + bbox[3] == pytest.approx(0.39)


def test_locate_falls_back_to_the_line_after_the_label():
    """An unreadable value still gets a box — which is exactly what a reviewer needs to see."""
    bbox, page = geometry.locate("���", _boxes(), label="Licence number")
    assert bbox == [0.1, 0.24, 0.18, 0.02]
    assert page == 1


def test_locate_never_guesses_when_nothing_matches():
    """The critical negative case: no match means no box, not a nearby one.

    A highlight box is a claim that the value is *there*. Guessing would put a confident
    rectangle over the wrong part of a KYC document.
    """
    assert geometry.locate("NOT-ON-THIS-PAGE", _boxes()) == (None, None)
    assert geometry.locate("CN-1234567", []) == (None, None)
    assert geometry.locate(None, _boxes()) == (None, None)


def test_locate_ignores_fragments_too_short_to_be_meaningful():
    """`LLC` appears on the page, but matching a 3-character fragment picks the wrong line."""
    bbox, _page = geometry.locate("XYZ LLC Holdings", _boxes())
    assert bbox is None


def test_read_confidence_is_none_without_a_match_or_a_measurement():
    assert geometry.read_confidence("CN-1234567", _boxes()) == pytest.approx(0.94)
    assert geometry.read_confidence("NOT-HERE", _boxes()) is None
    assert geometry.read_confidence("CN-1234567", []) is None
    no_score = [{"text": "CN-1234567", "page": 1, "bbox": [0, 0, 1, 1], "confidence": None}]
    assert geometry.read_confidence("CN-1234567", no_score) is None


# ------------------------------------------------------- document intelligence


def test_polygon_becomes_a_normalised_box():
    from app.azure.doc_intelligence import _normalise_polygon

    # An inch-based polygon on an 8.5 x 11 page: four corners, clockwise from top-left.
    box = _normalise_polygon([1.0, 2.0, 3.0, 2.0, 3.0, 2.5, 1.0, 2.5], 8.5, 11.0)
    assert box is not None
    x, y, w, h = box
    assert x == pytest.approx(1.0 / 8.5, abs=1e-4)
    assert y == pytest.approx(2.0 / 11.0, abs=1e-4)
    assert w == pytest.approx(2.0 / 8.5, abs=1e-4)
    assert h == pytest.approx(0.5 / 11.0, abs=1e-4)


def test_polygon_is_refused_rather_than_drawn_wrong():
    """Every degenerate input returns None. A box that cannot be trusted is not drawn."""
    from app.azure.doc_intelligence import _normalise_polygon

    assert _normalise_polygon([], 8.5, 11.0) is None
    assert _normalise_polygon([1.0, 2.0], 8.5, 11.0) is None
    # A page with no dimensions: nothing can be normalised against it.
    assert _normalise_polygon([1, 2, 3, 2, 3, 4, 1, 4], 0, 11.0) is None
    # A zero-area polygon would draw an invisible or inverted rectangle.
    assert _normalise_polygon([1, 2, 1, 2, 1, 2, 1, 2], 8.5, 11.0) is None


def test_polygon_outside_the_page_is_clamped_inside_it():
    from app.azure.doc_intelligence import _normalise_polygon

    box = _normalise_polygon([-1.0, -1.0, 20.0, -1.0, 20.0, 20.0, -1.0, 20.0], 8.5, 11.0)
    assert box is not None
    x, y, w, h = box
    assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
    assert x + w <= 1.0 and y + h <= 1.0


def test_demo_ocr_reports_no_geometry_rather_than_inventing_it():
    """The demo reader has no coordinates, so `line_boxes` stays empty and fields say so."""
    from app.quality.dataset import pdf_bytes, samples

    sample = next(s for s in samples() if s.quality == "clean")
    result = DemoOcr().read(pdf_bytes(sample.key), "application/pdf")
    assert result.text
    assert result.line_boxes == []
    assert result.has_geometry is False


def test_line_box_serialises_for_the_checkpoint():
    """It travels through the LangGraph state, so it has to be plain JSON."""
    box = LineBox(text="CN-1234567", page=1, bbox=[0.1, 0.2, 0.3, 0.04], confidence=0.93)
    assert json.loads(json.dumps(box.as_dict()))["bbox"] == [0.1, 0.2, 0.3, 0.04]
    assert OcrResult(text="", confidence=0.0, page_count=1).has_geometry is False


# ------------------------------------------------------------------ confidence


def test_read_signal_is_absent_without_a_measurement():
    """A missing signal must cost the field nothing — not be scored as zero."""
    assert confidence.read_signal(None) is None

    signal = confidence.read_signal(0.82)
    assert signal is not None
    assert signal.key == "read"
    assert signal.value == pytest.approx(0.82)


def test_read_signal_is_clamped_to_a_probability():
    for raw, expected in ((1.4, 1.0), (-0.2, 0.0)):
        signal = confidence.read_signal(raw)
        assert signal is not None and signal.value == expected


def test_the_sixth_signal_does_not_change_demo_scores():
    """The property that made a sixth signal safe to add.

    `combine()` divides by the weight of the signals actually present, so five signals score
    exactly what they scored before M6 — the new weight only participates when Document
    Intelligence supplied a measurement.
    """
    five = [
        confidence.ocr_signal(0.97),
        confidence.grounding("Al Noor", "Al Noor Trading LLC"),
        confidence.label_signal(matched_label=True, source_text="Company name"),
        confidence.shape("Al Noor", "string"),
        confidence.critic_signal(True),
    ]
    before = confidence.combine(list(five))
    with_absent_sixth = confidence.combine([*five, confidence.read_signal(None)])
    assert with_absent_sixth.raw == before.raw

    with_sixth = confidence.combine([*five, confidence.read_signal(0.4)])
    assert with_sixth.raw < before.raw  # a badly-read value scores lower, which is the point


# ---------------------------------------------------------------- structured output


def test_strict_schema_meets_azure_structured_output_rules():
    """Strict mode has three hard requirements, and all three are real constraints."""
    field_schema = [
        {"name": "license_number", "type": "string", "label_en": "Licence number"},
        {"name": "expiry_date", "type": "date", "label_en": "Expiry date"},
    ]
    schema = extraction_schema.strict_json_schema("trade_license", field_schema)

    # 1. Every property is required — including the optional ones, so a field the document
    #    does not contain comes back as an explicit null rather than a missing key.
    assert set(schema["required"]) == {"license_number", "expiry_date"}
    # 2. No extra properties.
    assert schema["additionalProperties"] is False
    # 3. Each field still accepts null, which is what makes (1) correct rather than a lie.
    for spec in schema["properties"].values():
        types = {entry.get("type") for entry in spec.get("anyOf", [])}
        assert "null" in types


def test_strict_schema_and_the_pydantic_validator_come_from_one_definition():
    """One schema, two jobs. If these ever diverge, a model could satisfy one and fail the other."""
    field_schema = [{"name": "expiry_date", "type": "date", "label_en": "Expiry"}]
    strict = extraction_schema.strict_json_schema("trade_license", field_schema)
    model = extraction_schema.build_model("trade_license", field_schema)
    assert set(strict["properties"]) == set(model.model_fields)


# -------------------------------------------------------------------- foundry


def test_foundry_marks_a_value_it_cannot_find_in_the_document():
    """The anti-hallucination rule, which is the whole reason the adapter re-checks the model.

    A returned value that is not in the source gets no source line and a zero confidence, so
    the grounding signal collapses and the field goes to a person.
    """
    from app.azure.foundry import FoundryExtractor

    lines = ["Licence number", "CN-1234567", "Company name", "Al Noor Trading LLC"]
    field_schema = [
        {"name": "license_number", "type": "string"},
        {"name": "company_name", "type": "string"},
    ]
    payload = {"license_number": "CN-1234567", "company_name": "Totally Invented Ltd"}

    found = FoundryExtractor._to_values(payload, field_schema, lines)

    assert found["license_number"].source_text == "CN-1234567"
    assert found["license_number"].confidence > 0
    # Present, but flagged: we report it rather than dropping it, so a reviewer sees what the
    # model said and that it is not in the document.
    assert found["company_name"].source_text is None
    assert found["company_name"].confidence == 0.0


def test_foundry_treats_a_null_as_absent_not_as_empty_text():
    from app.azure.foundry import FoundryExtractor

    field_schema = [{"name": "license_number", "type": "string"}]
    assert FoundryExtractor._to_values({"license_number": None}, field_schema, ["x"]) == {}
    assert FoundryExtractor._to_values({"license_number": "  "}, field_schema, ["x"]) == {}


class _Choice:
    def __init__(self, content: str | None, finish_reason: str = "stop") -> None:
        self.message = type("M", (), {"content": content})()
        self.finish_reason = finish_reason


class _Response:
    def __init__(self, choice: _Choice) -> None:
        self.choices = [choice]


def test_foundry_refuses_a_truncated_response():
    """Strict mode guarantees the shape of a *completed* response, not that it completed.

    Half a JSON object must never be parsed as a whole one.
    """
    from app.azure.foundry import FoundryExtractor

    with pytest.raises(ValueError, match="truncated"):
        FoundryExtractor._parse(_Response(_Choice('{"a":', finish_reason="length")))


def test_foundry_surfaces_a_content_filter_refusal():
    from app.azure.foundry import FoundryExtractor

    with pytest.raises(ValueError, match="content filter"):
        FoundryExtractor._parse(_Response(_Choice(None, finish_reason="content_filter")))


def test_foundry_refuses_an_empty_or_non_object_body():
    from app.azure.foundry import FoundryExtractor

    with pytest.raises(ValueError, match="empty"):
        FoundryExtractor._parse(_Response(_Choice(None)))
    with pytest.raises(ValueError, match="not an object"):
        FoundryExtractor._parse(_Response(_Choice("[1, 2]")))


def test_the_document_is_fenced_and_labelled_as_data():
    """A second line of defence behind the prompt shield: the document arrives marked as data."""
    from app.azure.foundry import _build_messages

    messages = _build_messages(
        prompt="Read the licence.", examples=None, doc_type="trade_license", text="LINE"
    )
    system = messages[0]["content"]
    # The "do not invent" rules are appended to, never replaced by, the registry's prompt.
    assert "Return a value ONLY if it appears" in system
    assert "Read the licence." in system
    assert messages[-1]["content"] == "<document>\nLINE\n</document>"


def test_few_shot_examples_become_a_user_assistant_pair():
    from app.azure.foundry import _build_messages

    messages = _build_messages(
        prompt=None,
        examples=[{"text": "EXAMPLE", "expected": {"license_number": "CN-1"}}],
        doc_type="trade_license",
        text="LINE",
    )
    roles = [message["role"] for message in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert json.loads(messages[2]["content"]) == {"license_number": "CN-1"}


def test_a_malformed_example_is_skipped_rather_than_sent():
    from app.azure.foundry import _build_messages

    messages = _build_messages(
        prompt=None,
        examples=[{"text": "", "expected": {}}, {"text": "OK", "expected": "not a dict"}],
        doc_type="trade_license",
        text="LINE",
    )
    assert [message["role"] for message in messages] == ["system", "user"]


# ----------------------------------------------------------------------- adls


def test_a_storage_path_splits_into_the_parts_the_sas_signer_wants():
    """Regression for a bug only a live call found.

    `generate_file_sas` takes `directory_name` and `file_name` as *separate* arguments, and
    `directory_name` is required even at the root. Passing the whole `case-id/file.pdf` as the
    file name raises a TypeError about a missing argument — which says nothing about the cause,
    and which `signed_url` then swallows into a `None`, so the viewer silently fell back to
    streaming bytes through the API with no error anywhere.
    """
    directory, _, file_name = "3f2b.../a1b2c3d4_licence.pdf".rpartition("/")
    assert directory == "3f2b..."
    assert file_name == "a1b2c3d4_licence.pdf"

    # A path with no directory still has to yield a usable pair rather than raising.
    directory, _, file_name = "licence.pdf".rpartition("/")
    assert directory == ""
    assert file_name == "licence.pdf"


def test_user_delegation_key_is_the_sas_credential(monkeypatch):
    """Match the real Data Lake SDK signature, not the similar Blob SDK keyword."""
    from app.azure import adls

    captured = {}
    delegation_key = object()

    def generate_file_sas(**kwargs):
        captured.update(kwargs)
        return "sig=offline"

    module = SimpleNamespace(
        FileSasPermissions=lambda **kwargs: kwargs,
        generate_file_sas=generate_file_sas,
    )
    monkeypatch.setattr(adls, "require_sdk", lambda *_: module)

    storage = object.__new__(adls.AdlsStorage)
    storage._account_url = "https://account.dfs.core.windows.net"
    storage._filesystem = "documents"
    storage._key = ""
    monkeypatch.setattr(storage, "_user_delegation_key", lambda: delegation_key)

    url = storage.signed_url(
        "case-id/document.pdf",
        content_type="application/pdf",
        filename="Customer document.pdf",
    )

    assert url is not None
    assert captured["credential"] is delegation_key
    assert "user_delegation_key" not in captured
    assert captured["directory_name"] == "case-id"
    assert captured["file_name"] == "document.pdf"
    assert captured["content_type"] == "application/pdf"
    assert captured["content_disposition"] == 'inline; filename="Customer_document.pdf"'


# --------------------------------------------------------------------- safety


def test_either_shield_flagging_is_enough():
    """Two detectors, and a miss costs far more than a false alarm."""
    from app.azure.safety import combine_shield
    from app.guardrails.shield import ShieldSignal, ShieldVerdict

    local_clean = ShieldVerdict(attacked=False, risk=0.0, engine="local")
    remote_hit = ShieldVerdict(
        attacked=True,
        risk=1.0,
        signals=[ShieldSignal(kind="prompt-shield", pattern="azure", excerpt="")],
        engine="azure",
    )

    combined = combine_shield(local_clean, remote_hit)
    assert combined.attacked is True
    assert combined.risk == 1.0
    assert "local+azure" in combined.engine

    # And the other way round: the local detector alone is still enough.
    local_hit = ShieldVerdict(attacked=True, risk=0.9, engine="local")
    remote_clean = ShieldVerdict(attacked=False, risk=0.0, engine="azure")
    assert combine_shield(local_hit, remote_clean).attacked is True


def test_no_remote_verdict_leaves_the_local_one_untouched():
    """"We could not check" must not become "we checked and it was clean"."""
    from app.azure.safety import combine_safety, combine_shield
    from app.guardrails.content_safety import SafetyVerdict
    from app.guardrails.shield import ShieldVerdict

    local = ShieldVerdict(attacked=True, risk=0.5, engine="local")
    assert combine_shield(local, None) is local

    safety = SafetyVerdict(flagged=False, severities={"hate": 0}, engine="local")
    assert combine_safety(safety, None) is safety


def test_the_higher_severity_per_category_wins():
    from app.azure.safety import combine_safety
    from app.guardrails.content_safety import SafetyVerdict

    local = SafetyVerdict(flagged=False, severities={"hate": 0, "violence": 2}, engine="local")
    remote = SafetyVerdict(flagged=True, severities={"hate": 4, "violence": 0}, engine="azure")

    combined = combine_safety(local, remote)
    assert combined.severities["hate"] == 4
    assert combined.severities["violence"] == 2
    assert combined.flagged is True
    assert set(combined.matches) == {"hate", "violence"}


# ---------------------------------------------------------------------- entra


def test_the_most_privileged_app_role_wins():
    from app.azure.entra import role_from_claims
    from app.db.enums import Role

    assert role_from_claims({"roles": ["Wathiq.Reviewer"]}) == Role.reviewer
    assert role_from_claims({"roles": ["Wathiq.Auditor", "Wathiq.Supervisor"]}) == Role.supervisor
    assert role_from_claims({"roles": ["Wathiq.Admin", "Wathiq.OpsOfficer"]}) == Role.admin
    # A single role may arrive as a bare string rather than a list.
    assert role_from_claims({"roles": "Wathiq.Admin"}) == Role.admin


def test_an_unrecognised_role_is_refused_not_downgraded():
    """Failing closed. Silently granting the lowest role would turn a misconfigured app
    registration into a person holding permissions nobody granted."""
    from app.azure.entra import EntraAuthError, role_from_claims

    with pytest.raises(EntraAuthError, match="no Wathiq role"):
        role_from_claims({"roles": ["SomeOtherApp.Admin"]})
    with pytest.raises(EntraAuthError):
        role_from_claims({})


def test_identity_prefers_the_tenant_wide_object_id():
    """`oid` is stable across app registrations; `sub` is only stable per application."""
    from app.azure.entra import identity_from_claims

    subject, email, name = identity_from_claims(
        {"oid": "OID-1", "sub": "SUB-1", "preferred_username": "Amina@Bank.AE", "name": "Amina"}
    )
    assert subject == "OID-1"
    assert email == "amina@bank.ae"  # normalised, because it is the lookup key
    assert name == "Amina"


def test_a_token_that_does_not_identify_a_user_is_refused():
    from app.azure.entra import EntraAuthError, identity_from_claims

    with pytest.raises(EntraAuthError):
        identity_from_claims({"oid": "OID-1"})  # no email of any kind
    with pytest.raises(EntraAuthError):
        identity_from_claims({"preferred_username": "a@b.c"})  # no subject


def test_entra_validation_refuses_before_it_is_configured():
    from app.azure.entra import EntraAuthError, validate_token

    with pytest.raises(EntraAuthError, match="not configured"):
        validate_token("any.token.here")


def test_only_rs256_is_accepted():
    """The classic JWT attack is a token asking to be verified with `none` or with HS256."""
    from app.azure.entra import ALGORITHMS

    assert ALGORITHMS == ["RS256"]


# -------------------------------------------------------------------- tracing


def test_span_is_a_no_op_when_tracing_is_off():
    """`span()` is called from graph nodes and tool calls, so it has to work with nothing
    installed and nothing configured."""
    from app.azure import monitor

    monitor.reset()
    assert monitor.enabled() is False
    with monitor.span("test.span", case_id="abc", count=1):
        pass
    monitor.annotate(verdict="clean")  # also a no-op, and must not raise


def test_an_exception_inside_a_span_still_propagates():
    from app.azure import monitor

    monitor.reset()
    with pytest.raises(ValueError, match="boom"), monitor.span("test.span"):
        raise ValueError("boom")


def test_tracing_stays_off_without_a_connection_string(monkeypatch):
    from app.azure import monitor
    from app.core.config import settings

    monkeypatch.setattr(settings, "azure_monitor_connection_string", "")
    monitor.reset()
    assert monitor.configure() is False


# ------------------------------------------------------------------- settings


@pytest.mark.asyncio
async def test_azure_services_can_use_local_demo_authentication(client, monkeypatch):
    """Provider mode and sign-in backend are independent deployment choices."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "mode", "azure")
    monkeypatch.setattr(settings, "auth_backend", "demo")

    users = await client.get("/api/v1/auth/demo-users")
    assert users.status_code == 200
    assert len(users.json()) == 5

    login = await client.post("/api/v1/auth/demo-login", json={"role": "reviewer"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "reviewer"


@pytest.mark.asyncio
async def test_entra_backend_never_exposes_demo_accounts(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_backend", "entra")
    users = await client.get("/api/v1/auth/demo-users")
    assert users.status_code == 200
    assert users.json() == []

    login = await client.post("/api/v1/auth/demo-login", json={"role": "reviewer"})
    assert login.status_code == 404


def test_a_service_is_off_until_its_own_endpoint_is_set(monkeypatch):
    """The rule that makes a half-configured deployment a legitimate state.

    `WATHIQ_MODE=azure` with only an OCR endpoint gives real OCR and the demo extractor — and
    the Settings screen says exactly that, rather than the system failing somewhere obscure.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "mode", "azure")
    monkeypatch.setattr(settings, "azure_doc_intelligence_endpoint", "https://ocr.example.com")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "")

    assert settings.doc_intelligence_enabled is True
    assert settings.foundry_enabled is False
    assert settings.adls_enabled is False
    assert settings.azure_search_enabled is False


def test_an_endpoint_alone_cannot_switch_a_demo_into_calling_a_paid_service(monkeypatch):
    """A stray endpoint in a developer's .env must not start billing them."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "mode", "demo")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://oai.example.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "gpt-4o-mini")
    monkeypatch.setattr(settings, "azure_doc_intelligence_endpoint", "https://ocr.example.com")

    assert settings.foundry_enabled is False
    assert settings.doc_intelligence_enabled is False


def test_foundry_needs_a_deployment_as_well_as_an_endpoint(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mode", "azure")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://oai.example.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "")
    assert settings.foundry_enabled is False


def test_the_factories_choose_the_demo_backends_in_demo_mode():
    from app.agent.extractor import DemoExtractor, get_extractor, reset_extractor
    from app.agent.ocr import DemoOcr as DemoOcrClass
    from app.agent.ocr import get_ocr, reset_ocr
    from app.rag.embedder import HashingEmbedder, get_embedder, reset_embedder
    from app.services.storage import LocalStorage, get_storage, reset_storage

    reset_ocr()
    reset_extractor()
    reset_storage()
    reset_embedder()
    assert isinstance(get_ocr(), DemoOcrClass)
    assert isinstance(get_extractor(), DemoExtractor)
    assert isinstance(get_storage(), LocalStorage)
    assert isinstance(get_embedder(), HashingEmbedder)


def test_a_local_backend_offers_no_signed_url():
    """`None` is the honest answer for a folder, and the endpoint then streams the bytes."""
    from app.services.storage import get_storage

    assert get_storage().signed_url("anything") is None


def test_described_services_never_include_a_key(monkeypatch):
    from app.azure import describe_azure_services
    from app.core.config import settings

    monkeypatch.setattr(settings, "mode", "azure")
    monkeypatch.setattr(settings, "azure_openai_api_key", "super-secret-key-value")
    monkeypatch.setattr(settings, "azure_content_safety_key", "another-secret")
    monkeypatch.setattr(
        settings, "azure_monitor_connection_string", "InstrumentationKey=secret-key"
    )

    rendered = json.dumps(describe_azure_services())
    assert "super-secret-key-value" not in rendered
    assert "another-secret" not in rendered
    assert "InstrumentationKey" not in rendered


def test_describe_credential_says_how_without_saying_what():
    from app.azure.credentials import describe_credential

    assert describe_credential("a-real-key") == "API key"
    assert describe_credential("  ") == "Managed identity (Entra)"


# ---------------------------------------------------------------- offline promise


def test_demo_mode_loads_no_azure_sdk():
    """The promise M1 made and M6 has to keep.

    The SDKs are installed in the image, so an import would succeed and nothing would look
    wrong — which is exactly why this has to be asserted rather than assumed. Every adapter
    imports its SDK inside the function that needs it.
    """
    import subprocess
    import sys

    probe = """
import sys
from app.agent.graph import build_graph
from app.agent.extractor import get_extractor
from app.agent.ocr import get_ocr
from app.main import app
from app.rag.embedder import get_embedder
from app.services.storage import get_storage

build_graph(); get_ocr(); get_extractor(); get_storage(); get_embedder()

leaked = sorted(
    name for name in sys.modules
    if name.split(".")[0] in {"openai", "azure"} and not name.startswith("app.azure")
)
print(",".join(leaked))
"""
    # A subprocess, because this test file's own imports have already pulled the SDKs in.
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    leaked = [name for name in result.stdout.strip().split(",") if name]
    assert leaked == [], f"demo mode imported Azure SDK modules: {leaked}"


# ------------------------------------------------------------------- fit job


def test_the_calibration_job_parses_what_azure_ml_sends_it():
    from app.quality.fit_job import parse_samples

    assert parse_samples('[[0.9, true], [0.2, false]]') == [(0.9, True), (0.2, False)]


def test_the_calibration_job_refuses_malformed_input():
    """It fails in the job, where the cause is visible — not later as a curve fitted on
    fewer points than intended."""
    from app.quality.fit_job import parse_samples

    with pytest.raises(ValueError, match="must be a JSON array"):
        parse_samples('{"not": "an array"}')
    with pytest.raises(ValueError, match="not a \\[score, correct\\] pair"):
        parse_samples("[[0.9]]")


def test_the_job_writes_a_curve_the_adapter_can_read_back(tmp_path):
    """End to end through the script, with the same maths the in-process path uses."""
    from app.quality.fit_job import main

    samples = [[0.9, True], [0.2, False]] * 12
    assert main(["--samples", json.dumps(samples), "--output-dir", str(tmp_path)]) == 0

    body = json.loads((tmp_path / "curve.json").read_text(encoding="utf-8"))
    assert {"a", "b", "fitted", "sample_count", "brier_before", "brier_after"} <= set(body)
    assert body["sample_count"] == 24
