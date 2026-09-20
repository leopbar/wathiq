"""Tests for the assurance machinery: rule packs, confidence, calibration and retrieval.

These are the parts a reviewer's trust rests on, so each test says what would go wrong for a
person if the behaviour were different.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.agent import calibration, confidence, rulepacks
from app.agent import rules as rule_engine
from app.rag import chunking, fewshot
from app.rag.embedder import HashingEmbedder, cosine


class TestRulePacks:
    def test_every_document_type_has_a_versioned_pack(self) -> None:
        packs = {pack.id: pack for pack in rulepacks.all_packs()}
        assert {
            "trade_license",
            "emirates_id",
            "passport",
            "moa",
            "salary_certificate",
        } <= set(packs)
        for pack in packs.values():
            assert pack.version.count(".") == 2, f"{pack.id} version is not semver"
            assert pack.rules, f"{pack.id} has no rules"

    def test_a_pack_is_found_by_document_type(self) -> None:
        pack = rulepacks.pack_for("trade_license")
        assert pack is not None
        assert pack.reference == f"trade_license@{pack.version}"

    def test_an_unknown_document_type_has_no_pack(self) -> None:
        """So the engine falls back to the editable rows and records that it did."""
        assert rulepacks.pack_for("unknown") is None

    def test_every_rule_has_an_id_a_message_and_a_policy(self) -> None:
        """A finding a reviewer cannot trace back to a policy is not actionable."""
        for pack in rulepacks.all_packs():
            for rule in pack.rules:
                assert rule.get("id"), f"{pack.id}: rule without an id"
                assert rule.get("message"), f"{pack.id}/{rule.get('id')}: no message"
                assert rule.get("policy"), f"{pack.id}/{rule.get('id')}: no policy citation"
                assert rule.get("explain"), f"{pack.id}/{rule.get('id')}: no explanation"

    def test_every_named_check_a_pack_refers_to_exists(self) -> None:
        """A typo in a pack would otherwise mean a rule silently never runs."""
        registered = set(rule_engine.registered_checks())
        for pack in rulepacks.all_packs():
            for rule in pack.rules:
                if "check" in rule:
                    assert rule["check"] in registered, f"{pack.id}: unknown check {rule['check']}"


class TestRuleEngine:
    today = date(2026, 6, 1)

    def _run(self, expr: str, values: dict[str, str | None], doc_type: str = "trade_license"):
        return rule_engine.evaluate(
            [{"id": "R", "expr": expr, "severity": "warning"}],
            {doc_type: values},
            doc_type,
            today=self.today,
        )[0]

    def test_a_date_in_the_future_passes(self) -> None:
        assert self._run("expiry_date > today", {"expiry_date": "2030-01-10"}).passed

    def test_a_date_in_the_past_fails(self) -> None:
        assert not self._run("expiry_date > today", {"expiry_date": "2020-01-10"}).passed

    def test_a_date_offset_in_months(self) -> None:
        """Six months of remaining validity — the passport rule."""
        soon = (self.today + timedelta(days=100)).isoformat()
        far = (self.today + timedelta(days=400)).isoformat()
        assert not self._run("expiry_date > today + 6 months", {"expiry_date": soon}).passed
        assert self._run("expiry_date > today + 6 months", {"expiry_date": far}).passed

    def test_a_date_offset_in_days(self) -> None:
        recent = (self.today - timedelta(days=10)).isoformat()
        old = (self.today - timedelta(days=200)).isoformat()
        assert self._run("issue_date > today - 90 days", {"issue_date": recent}).passed
        assert not self._run("issue_date > today - 90 days", {"issue_date": old}).passed

    def test_numbers_compare_with_currency_and_separators(self) -> None:
        outcome = self._run(
            "total_salary >= basic_salary",
            {"total_salary": "AED 31,500", "basic_salary": "AED 22,000"},
            doc_type="salary_certificate",
        )
        assert outcome.passed

    def test_a_total_below_the_basic_fails(self) -> None:
        outcome = self._run(
            "total_salary >= basic_salary",
            {"total_salary": "AED 12,000", "basic_salary": "AED 22,000"},
            doc_type="salary_certificate",
        )
        assert not outcome.passed

    def test_a_shape_template_matches_an_emirates_id(self) -> None:
        good = self._run(
            "id_number matches 784-####-#######-#",
            {"id_number": "784-1987-1234567-1"},
            doc_type="emirates_id",
        )
        bad = self._run(
            "id_number matches 784-####-#######-#",
            {"id_number": "999-1-2"},
            doc_type="emirates_id",
        )
        assert good.passed and not bad.passed

    def test_an_iban_template_allows_optional_spacing(self) -> None:
        """A UAE IBAN is written with and without spaces; both are the same IBAN."""
        spaced = self._run(
            "iban matches AE## #### #### #### #### ###",
            {"iban": "AE07 0331 2345 6789 0123 456"},
            doc_type="salary_certificate",
        )
        tight = self._run(
            "iban matches AE## #### #### #### #### ###",
            {"iban": "AE070331234567890123456"},
            doc_type="salary_certificate",
        )
        assert spaced.passed and tight.passed

    def test_presence(self) -> None:
        assert self._run("license_number is present", {"license_number": "CN-1"}).passed
        assert not self._run("license_number is present", {"license_number": ""}).passed

    def test_a_missing_value_is_not_evaluated_rather_than_passed(self) -> None:
        outcome = self._run("expiry_date > today", {})
        assert outcome.evaluated is False

    def test_a_named_check_runs(self) -> None:
        outcome = rule_engine.evaluate(
            [{"id": "MOA_SHAREHOLDERS_HAVE_ID", "check": "shareholders_have_id",
              "severity": "critical"}],
            {
                "moa": {"shareholders": "Hamad Al Suwaidi (60%), Priya Nair (40%)"},
                "emirates_id": {"full_name_en": "Hamad Al Suwaidi"},
            },
            "moa",
            today=self.today,
        )[0]
        assert outcome.evaluated is True
        assert outcome.passed is False
        assert "Priya Nair" in outcome.detail

    def test_shares_totalling_100_pass(self) -> None:
        outcome = rule_engine.evaluate(
            [{"id": "R", "check": "shares_total_100", "severity": "warning"}],
            {"moa": {"shareholders": "A (60%), B (40%)"}},
            "moa",
            today=self.today,
        )[0]
        assert outcome.passed is True

    def test_the_outcome_records_which_pack_judged_it(self) -> None:
        outcome = rule_engine.evaluate(
            [{"id": "R", "expr": "expiry_date > today", "severity": "warning"}],
            {"trade_license": {"expiry_date": "2020-01-01"}},
            "trade_license",
            today=self.today,
            pack_id="trade_license",
            pack_version="1.2.0",
        )[0]
        assert (outcome.pack, outcome.pack_version) == ("trade_license", "1.2.0")


class TestConfidenceSignals:
    def test_a_grounded_value_scores_full_marks(self) -> None:
        signal = confidence.grounding("CN-1042288", "LICENCE NUMBER\nCN-1042288")
        assert signal.value == 1.0

    def test_a_value_that_is_not_in_the_document_scores_zero(self) -> None:
        """The most important signal in the system: a value we cannot find is a value we
        cannot trust, whatever else looks fine."""
        signal = confidence.grounding("CN-9999999", "LICENCE NUMBER\nCN-1042288")
        assert signal.value == 0.0

    def test_shape_checks_the_type_the_schema_asked_for(self) -> None:
        assert confidence.shape("2030-01-10", "date").value == 1.0
        assert confidence.shape("not a date", "date").value == 0.0
        assert confidence.shape("AED 22,000", "number").value == 1.0

    def test_a_missing_critic_signal_does_not_punish_the_field(self) -> None:
        """Before the critic runs, its signal is absent, not zero."""
        assert confidence.critic_signal(None) is None
        signals = [confidence.ocr_signal(1.0), confidence.grounding("x", "x")]
        assert confidence.combine(signals).raw == 1.0

    def test_a_critic_disagreement_lowers_the_score(self) -> None:
        base = [confidence.ocr_signal(1.0), confidence.grounding("x", "x")]
        agreed = confidence.combine([*base, confidence.critic_signal(True)]).raw
        disagreed = confidence.combine([*base, confidence.critic_signal(False)]).raw
        assert disagreed < agreed

    def test_self_correction_costs_a_little_confidence(self) -> None:
        signals = [confidence.ocr_signal(1.0), confidence.grounding("x", "x")]
        clean = confidence.combine(signals, self_corrections=0).raw
        repaired = confidence.combine(signals, self_corrections=2).raw
        assert clean - repaired == pytest.approx(2 * confidence.SELF_CORRECTION_PENALTY)

    def test_the_breakdown_names_the_weakest_signal(self) -> None:
        breakdown = confidence.combine(
            [confidence.ocr_signal(1.0), confidence.grounding("nope", "other text")]
        )
        weakest = breakdown.weakest
        assert weakest is not None and weakest.key == "grounded"


class TestCalibration:
    def test_an_unfitted_curve_returns_the_raw_score_unchanged(self) -> None:
        """Honesty rule: an uncalibrated number is shown as raw, never dressed up."""
        curve = calibration.CalibrationCurve()
        assert curve.fitted is False
        assert curve.apply(0.73) == 0.73

    def test_too_few_samples_refuses_to_fit(self) -> None:
        curve = calibration.fit([(0.9, True), (0.8, False)])
        assert curve.fitted is False

    def test_all_correct_refuses_to_fit(self) -> None:
        """There is no curve to learn when nothing was ever wrong."""
        curve = calibration.fit([(0.9, True)] * 40)
        assert curve.fitted is False

    def test_an_overconfident_extractor_is_pulled_down(self) -> None:
        # Says 0.95 but is only right about half the time.
        samples = [(0.95, index % 2 == 0) for index in range(60)]
        curve = calibration.fit(samples)
        assert curve.fitted is True
        assert curve.apply(0.95) < 0.95

    def test_fitting_improves_the_brier_score(self) -> None:
        samples = [(0.9, index % 3 != 0) for index in range(90)]
        curve = calibration.fit(samples)
        assert curve.improvement >= 0

    def test_reliability_bins_compare_what_we_said_with_what_happened(self) -> None:
        samples = [(0.9, index % 2 == 0) for index in range(40)]
        bins = calibration.reliability(samples)
        assert bins
        assert all(0.0 <= point.observed <= 1.0 for point in bins)
        assert sum(point.n for point in bins) == len(samples)


class TestPolicyRetrieval:
    def test_the_corpus_splits_into_cited_sections(self) -> None:
        chunks = chunking.load_corpus()
        assert len(chunks) > 20
        citations = {chunk.citation for chunk in chunks}
        # The sections the rule packs cite must exist, or a finding would quote nothing.
        assert "KYC-POL-004 §3.2" in citations
        assert "KYC-POL-006 §4.1" in citations
        assert "LEN-POL-002 §1.1" in citations

    def test_every_policy_citation_in_every_rule_pack_resolves(self) -> None:
        """The check that stops a rule pack citing a section that does not exist."""
        citations = {chunk.citation for chunk in chunking.load_corpus()}
        for pack in rulepacks.all_packs():
            for rule in pack.rules:
                assert rule["policy"] in citations, f"{pack.id}/{rule['id']} cites {rule['policy']}"

    def test_the_embedder_is_stable_across_calls(self) -> None:
        """A randomised hash would silently rot the index after a restart."""
        embedder = HashingEmbedder()
        assert embedder.embed("expired trade licence") == embedder.embed("expired trade licence")

    def test_similar_text_scores_higher_than_unrelated_text(self) -> None:
        embedder = HashingEmbedder()
        query = embedder.embed("the trade licence is expired")
        close = embedder.embed("a file may not be refreshed on an expired trade licence")
        far = embedder.embed("shareholding percentages must total one hundred")
        assert cosine(query, close) > cosine(query, far)

    def test_a_chunk_quote_is_short_enough_to_show(self) -> None:
        from app.rag.index import Retrieved

        chunk = chunking.load_corpus()[0]
        retrieved = Retrieved(
            citation=chunk.citation,
            policy_id=chunk.policy_id,
            policy_title=chunk.policy_title,
            section=chunk.section,
            heading=chunk.heading,
            text=chunk.text,
            similarity=1.0,
        )
        assert 0 < len(retrieved.quote) <= len(chunk.text)


class TestFewShotSelection:
    def test_examples_load_for_the_configured_document_types(self) -> None:
        fewshot.reload()
        types = {example.doc_type for example in fewshot.load_examples()}
        assert {"trade_license", "salary_certificate"} <= types

    def test_a_free_zone_licence_selects_the_free_zone_example_first(self) -> None:
        fewshot.reload()
        chosen = fewshot.select(
            "trade_license",
            "TRADE LICENCE (FREE ZONE)\nLicensing authority\nFree Zone Authority\n"
            "Business activity\nFreight forwarding",
            k=1,
        )
        assert chosen
        assert chosen[0].example.id == "tl_freezone_abbrev"

    def test_selection_never_returns_examples_of_another_document_type(self) -> None:
        fewshot.reload()
        chosen = fewshot.select("salary_certificate", "SALARY CERTIFICATE\nBasic salary", k=5)
        assert {selection.example.doc_type for selection in chosen} == {"salary_certificate"}


class TestRuleGuards:
    """A rule can say when it applies. Without that, two rules fire for one fact."""

    today = date(2026, 6, 1)

    def _run(self, rule: dict[str, object], values: dict[str, str | None]):
        return rule_engine.evaluate(
            [rule], {"trade_license": values}, "trade_license", today=self.today
        )[0]

    def test_a_guard_that_holds_lets_the_rule_run(self) -> None:
        outcome = self._run(
            {
                "id": "TL_EXPIRES_SOON",
                "expr": "expiry_date > today + 30 days",
                "when": "expiry_date > today",
                "severity": "info",
            },
            {"expiry_date": "2026-06-10"},
        )
        assert outcome.evaluated is True
        assert outcome.passed is False  # valid, but expiring within 30 days

    def test_an_already_expired_licence_does_not_also_report_expiring_soon(self) -> None:
        outcome = self._run(
            {
                "id": "TL_EXPIRES_SOON",
                "expr": "expiry_date > today + 30 days",
                "when": "expiry_date > today",
                "severity": "info",
            },
            {"expiry_date": "2019-06-01"},
        )
        assert outcome.evaluated is False
        assert "guard" in outcome.detail
