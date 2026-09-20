"""Tests for the M3 reasoning steps: workers, self-correction, critic, investigator, tools.

This is the "agent" band of the test plan: routing, interrupts, tool calls and loop limits.
The MCP servers are exercised in-process through the official client, so these tests need no
containers beyond the one they run in.
"""

from __future__ import annotations

import pytest

from app.agent import critic as critic_module
from app.agent import investigator as investigator_module
from app.agent import schema as extraction_schema
from app.agent import worker as worker_module
from app.agent.state import merge_fields
from app.agent.tools import NODE_TOOLS, SERVERS, ToolBroker, ToolCall, ToolNotAllowed

TRADE_LICENCE_SCHEMA: list[dict[str, object]] = [
    {"name": "license_number", "label_en": "Licence number", "type": "string", "is_critical": True},
    {"name": "company_name_en", "label_en": "Company name (EN)", "type": "string",
     "is_critical": True},
    {"name": "issue_date", "label_en": "Issue date", "type": "date"},
    {"name": "expiry_date", "label_en": "Expiry date", "type": "date", "is_critical": True},
]


def _document(text: str) -> dict[str, object]:
    return {
        "document_id": "doc-1",
        "filename": "trade_licence.pdf",
        "doc_type": "trade_license",
        "storage_path": "case/trade_licence.pdf",
        "ocr_text": text,
        "safe_text": text,
        "ocr_confidence": 0.97,
    }


CLEAN_TEXT = "\n".join(
    [
        "TRADE LICENCE",
        "LICENCE NUMBER",
        "CN-1042288",
        "COMPANY NAME (EN)",
        "Falcon Ridge Trading LLC",
        "ISSUE DATE",
        "2016-03-11",
        "EXPIRY DATE",
        "2030-01-10",
    ]
)


class TestRuntimeSchema:
    def test_a_model_is_built_from_configuration(self) -> None:
        model = extraction_schema.build_model("trade_license", TRADE_LICENCE_SCHEMA)
        assert set(model.model_fields) == {
            "license_number",
            "company_name_en",
            "issue_date",
            "expiry_date",
        }

    def test_a_bad_date_is_a_named_validation_error(self) -> None:
        """The repair pass needs the field name and the reason, not just 'invalid'."""
        model = extraction_schema.build_model("trade_license", TRADE_LICENCE_SCHEMA)
        ok, errors = extraction_schema.validate(model, {"expiry_date": "not a date"})
        assert ok is False
        assert errors[0].field == "expiry_date"
        assert "date" in errors[0].message

    def test_an_absent_value_is_valid(self) -> None:
        """A field the document does not contain must produce None, not an invention."""
        model = extraction_schema.build_model("trade_license", TRADE_LICENCE_SCHEMA)
        ok, _errors = extraction_schema.validate(model, {"expiry_date": None})
        assert ok is True

    def test_the_json_schema_is_publishable(self) -> None:
        """This is what a structured-output call sends in Azure mode."""
        published = extraction_schema.json_schema("trade_license", TRADE_LICENCE_SCHEMA)
        assert published["properties"]["expiry_date"]


class TestWorkerSelfCorrection:
    def test_a_clean_document_needs_no_repair(self) -> None:
        fields, report = worker_module.extract_document(_document(CLEAN_TEXT),
                                                        TRADE_LICENCE_SCHEMA)
        values = {field["name"]: field["value"] for field in fields}
        assert values["expiry_date"] == "2030-01-10"
        assert report["repairs"] == []
        assert report["attempts"] == 1
        assert report["validated"] is True

    def test_an_inline_label_is_repaired(self) -> None:
        """'Expiry date: 2030-01-10' on one line — the label reader misses it, the repair
        pass finds it."""
        text = CLEAN_TEXT.replace("EXPIRY DATE\n2030-01-10", "Expiry date: 2030-01-10")
        fields, report = worker_module.extract_document(_document(text), TRADE_LICENCE_SCHEMA)
        values = {field["name"]: field["value"] for field in fields}
        assert values["expiry_date"] == "2030-01-10"
        assert report["validated"] is True

    def test_a_value_that_never_validates_is_emptied_not_stored(self) -> None:
        """A stored value that fails its own schema looks like an answer. Worse than nothing."""
        text = CLEAN_TEXT.replace("2030-01-10", "sometime next year")
        fields, report = worker_module.extract_document(_document(text), TRADE_LICENCE_SCHEMA)
        values = {field["name"]: field["value"] for field in fields}
        assert values["expiry_date"] is None
        assert report["validated"] is True
        assert any(repair["strategy"] == "drop" for repair in report["repairs"])

    def test_the_repair_loop_is_bounded(self) -> None:
        text = CLEAN_TEXT.replace("2030-01-10", "???").replace("2016-03-11", "???")
        _fields, report = worker_module.extract_document(_document(text), TRADE_LICENCE_SCHEMA)
        assert report["attempts"] <= 1 + worker_module.MAX_REPAIRS

    def test_every_repair_explains_itself(self) -> None:
        text = CLEAN_TEXT.replace("EXPIRY DATE\n2030-01-10", "Expiry date: 2030-01-10")
        _fields, report = worker_module.extract_document(_document(text), TRADE_LICENCE_SCHEMA)
        for repair in report["repairs"]:
            assert repair["field"] and repair["error"] and repair["explanation"]

    def test_a_repaired_field_scores_lower_than_a_clean_one(self) -> None:
        clean, _ = worker_module.extract_document(_document(CLEAN_TEXT), TRADE_LICENCE_SCHEMA)
        text = CLEAN_TEXT.replace("EXPIRY DATE\n2030-01-10", "Expiry date: 2030-01-10")
        repaired, _ = worker_module.extract_document(_document(text), TRADE_LICENCE_SCHEMA)
        clean_score = {f["name"]: f["confidence"] for f in clean}["expiry_date"]
        repaired_score = {f["name"]: f["confidence"] for f in repaired}["expiry_date"]
        assert repaired_score < clean_score

    def test_every_field_carries_the_signals_behind_its_score(self) -> None:
        fields, _report = worker_module.extract_document(_document(CLEAN_TEXT),
                                                         TRADE_LICENCE_SCHEMA)
        signals = {signal["key"] for signal in fields[0]["signals"]}
        assert {"ocr", "grounded", "label", "shape"} <= signals

    def test_the_worker_selects_few_shot_examples(self) -> None:
        _fields, report = worker_module.extract_document(_document(CLEAN_TEXT),
                                                         TRADE_LICENCE_SCHEMA)
        assert report["examples"], "no examples were selected for the prompt"


class TestFieldReducer:
    def test_parallel_workers_do_not_collide(self) -> None:
        a = [{"document_id": "d1", "name": "x", "order_index": 0}]
        b = [{"document_id": "d2", "name": "x", "order_index": 100}]
        assert len(merge_fields(a, b)) == 2

    def test_the_critic_replaces_a_field_instead_of_duplicating_it(self) -> None:
        original = [{"document_id": "d1", "name": "x", "order_index": 0, "confidence": 0.9}]
        revised = [{"document_id": "d1", "name": "x", "order_index": 0, "confidence": 0.4}]
        merged = merge_fields(original, revised)
        assert len(merged) == 1
        assert merged[0]["confidence"] == 0.4

    def test_order_is_stable(self) -> None:
        merged = merge_fields(
            [{"document_id": "d", "name": "b", "order_index": 2}],
            [{"document_id": "d", "name": "a", "order_index": 1}],
        )
        assert [field["name"] for field in merged] == ["a", "b"]


class TestCritic:
    async def test_it_agrees_with_a_grounded_value(self) -> None:
        verdict = await critic_module.review_field(
            {"name": "license_number", "value": "CN-1042288"},
            document=_document(CLEAN_TEXT),
            expected_type="string",
            label_keys=critic_module.label_index(TRADE_LICENCE_SCHEMA),
        )
        assert verdict.agreed is True

    async def test_it_rejects_a_value_that_is_not_on_the_page(self) -> None:
        """The invented-value case. This is the check that matters most."""
        verdict = await critic_module.review_field(
            {"name": "license_number", "value": "CN-0000000"},
            document=_document(CLEAN_TEXT),
            expected_type="string",
            label_keys=critic_module.label_index(TRADE_LICENCE_SCHEMA),
        )
        assert verdict.agreed is False
        assert "could not be found" in verdict.reason

    async def test_it_rejects_a_value_of_the_wrong_shape(self) -> None:
        verdict = await critic_module.review_field(
            {"name": "expiry_date", "value": "Falcon Ridge Trading LLC"},
            document=_document(CLEAN_TEXT),
            expected_type="date",
            label_keys=critic_module.label_index(TRADE_LICENCE_SCHEMA),
        )
        assert verdict.agreed is False

    async def test_it_catches_a_value_taken_from_the_wrong_label(self) -> None:
        """The most common real extraction error: the line under the wrong heading."""
        verdict = await critic_module.review_field(
            {"name": "expiry_date", "value": "2016-03-11"},
            document=_document(CLEAN_TEXT),
            expected_type="date",
            label_keys=critic_module.label_index(TRADE_LICENCE_SCHEMA),
        )
        assert verdict.agreed is False
        assert "issue_date" in verdict.reason

    async def test_an_empty_field_is_not_a_disagreement(self) -> None:
        verdict = await critic_module.review_field(
            {"name": "expiry_date", "value": None},
            document=_document(CLEAN_TEXT),
            expected_type="date",
            label_keys=critic_module.label_index(TRADE_LICENCE_SCHEMA),
        )
        assert verdict.agreed is True


class TestLeastPrivilege:
    def test_the_investigator_cannot_reach_core_banking(self) -> None:
        """The single most important permission in the system."""
        broker = ToolBroker.for_node("investigator")
        assert broker.may_call("core_banking", "post_kyc_refresh") is False

    async def test_calling_a_forbidden_tool_raises_before_any_request(self) -> None:
        broker = ToolBroker.for_node("investigator")
        with pytest.raises(ToolNotAllowed):
            await broker.call("core_banking", "post_kyc_refresh", case_id="x")
        assert broker.calls == [], "a refused call must not appear as an attempt"

    def test_the_critic_has_only_the_one_read_tool_it_needs(self) -> None:
        assert NODE_TOOLS["critic"] == {"document_store": ["find_in_document"]}

    def test_only_core_banking_can_write(self) -> None:
        writers = {key for key, (_n, _a, writes) in SERVERS.items() if writes}
        assert writers == {"core_banking"}

    def test_every_allowlisted_server_exists(self) -> None:
        for node, servers in NODE_TOOLS.items():
            for server in servers:
                assert server in SERVERS, f"{node} refers to unknown server {server}"


class FakeBroker(ToolBroker):
    """A broker that answers from a script instead of calling a server.

    Used to test the investigator's reasoning without pinning the test to the contents of the
    simulated registry. The MCP servers themselves are tested separately.
    """

    def __init__(self, answers: dict[str, dict]) -> None:
        super().__init__(node="investigator", allowed=NODE_TOOLS["investigator"])
        self.answers = answers

    async def call(self, server: str, tool: str, **arguments) -> ToolCall:  # type: ignore[override]
        if not self.may_call(server, tool):
            raise ToolNotAllowed(f"{server}.{tool}")
        payload = self.answers.get(tool)
        call = ToolCall(
            server=server,
            tool=tool,
            arguments=arguments,
            ok=payload is not None,
            duration_ms=1,
            result=payload,
            error=None if payload is not None else "no scripted answer",
        )
        self.calls.append(call)
        return call


class TestInvestigator:
    def test_it_always_plans_to_screen_every_named_party(self) -> None:
        questions = investigator_module.plan(
            {
                "trade_license": {"company_name_en": "Falcon Ridge Trading LLC",
                                  "license_number": "CN-1042288"},
                "emirates_id": {"full_name_en": "Hamad Al Suwaidi"},
            }
        )
        screened = {q.payload["name"] for q in questions if q.kind == "sanctions"}
        assert screened == {"Falcon Ridge Trading LLC", "Hamad Al Suwaidi"}

    def test_a_name_mismatch_becomes_a_reconciliation_question(self) -> None:
        questions = investigator_module.plan(
            {
                "trade_license": {"company_name_en": "Falcon Ridge Trading LLC"},
                "moa": {"company_name_en": "Blue Horizon Shipping"},
            }
        )
        assert any(q.kind == "company_name_mismatch" for q in questions)

    def test_matching_names_are_not_investigated(self) -> None:
        """A spelling difference is not a mismatch; asking anyway wastes a tool call."""
        questions = investigator_module.plan(
            {
                "trade_license": {"company_name_en": "Al Noor Logistics LLC"},
                "moa": {"company_name_en": "Al Noor Logistics L.L.C."},
            }
        )
        assert not any(q.kind == "company_name_mismatch" for q in questions)

    async def test_a_possible_sanctions_match_always_goes_to_a_human(self) -> None:
        broker = FakeBroker(
            {
                "screen_name": {
                    "band": "possible",
                    "matches": [{"matched_name": "Yousef Karem", "score": 0.83}],
                }
            }
        )
        questions = [
            investigator_module.Question(
                kind="sanctions",
                prompt="screen",
                payload={"name": "Youssef Karam", "entity_type": "person"},
            )
        ]
        outcome = await investigator_module.investigate(questions, broker)
        codes = {finding["code"] for finding in outcome.findings}
        assert "SANCTIONS_POSSIBLE_MATCH" in codes
        assert any(r["code"] == "SANCTIONS_POSSIBLE_MATCH" for r in outcome.review_reasons)

    async def test_a_clear_screening_raises_nothing_but_is_still_recorded(self) -> None:
        broker = FakeBroker({"screen_name": {"band": "none", "matches": []}})
        questions = [
            investigator_module.Question(
                kind="sanctions", prompt="screen",
                payload={"name": "Hamad Al Suwaidi", "entity_type": "person"},
            )
        ]
        outcome = await investigator_module.investigate(questions, broker)
        assert outcome.findings == []
        assert len(outcome.steps) == 1
        assert "no match" in outcome.steps[0].observation

    async def test_a_failed_tool_call_never_looks_like_a_passed_check(self) -> None:
        """If screening could not run, the case must not proceed as though it had."""
        broker = FakeBroker({})  # nothing answers
        questions = [
            investigator_module.Question(
                kind="sanctions", prompt="screen",
                payload={"name": "Hamad Al Suwaidi", "entity_type": "person"},
            )
        ]
        outcome = await investigator_module.investigate(questions, broker)
        assert {f["code"] for f in outcome.findings} == {"SCREENING_UNAVAILABLE"}
        assert outcome.review_reasons

    async def test_the_react_loop_stops_at_its_limit(self) -> None:
        broker = FakeBroker({"screen_name": {"band": "none", "matches": []}})
        questions = [
            investigator_module.Question(
                kind="sanctions", prompt="screen",
                payload={"name": f"Person {index}", "entity_type": "person"},
            )
            for index in range(investigator_module.MAX_STEPS + 3)
        ]
        outcome = await investigator_module.investigate(questions, broker)
        assert len(outcome.steps) == investigator_module.MAX_STEPS
        assert {f["code"] for f in outcome.findings} == {"INVESTIGATION_INCOMPLETE"}

    async def test_every_step_records_thought_action_and_observation(self) -> None:
        broker = FakeBroker({"screen_name": {"band": "none", "matches": []}})
        questions = [
            investigator_module.Question(
                kind="sanctions", prompt="Is X on the list?",
                payload={"name": "X", "entity_type": "person"},
            )
        ]
        outcome = await investigator_module.investigate(questions, broker)
        step = outcome.steps[0].as_dict()
        assert step["thought"] and step["action"] and step["observation"]
