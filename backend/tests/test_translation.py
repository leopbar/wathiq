"""Showing an Arabic value in English, without changing what the document said.

The property that matters most here is the one a bank would ask about first: a translation is
a reading aid, and the value stays exactly as the document wrote it. Everything else — the
glossary, the model backend, what is left alone — is detail beneath that.
"""

from __future__ import annotations

import pytest

from app.agent import translate as translation
from app.agent.translate import (
    GlossaryTranslator,
    Translation,
    TranslatorBackend,
    needs_translation,
    translate_values,
)

ARABIC_ACTIVITY = "تجارة عامة"  # general trading
ARABIC_LLC = "ذ.م.م"  # LLC
ARABIC_NAME = "فالكون ريدج"  # Falcon Ridge


class TestWhatNeedsTranslating:
    def test_arabic_prose_does(self) -> None:
        assert needs_translation(ARABIC_ACTIVITY) is True

    @pytest.mark.parametrize(
        "value",
        [
            "CN-1042288",  # a licence number
            "2027-03-15",  # a date
            "AE07 0331 2345 6789 0123 456",  # an IBAN
            "18000",
            "Falcon Ridge Trading LLC",  # already English
            "",
            None,
        ],
    )
    def test_identifiers_and_english_do_not(self, value: str | None) -> None:
        """Translating an identifier would corrupt it; translating English is pointless."""
        assert needs_translation(value) is False


class TestTheGlossary:
    def test_a_standard_term_is_translated(self) -> None:
        assert GlossaryTranslator().translate([ARABIC_ACTIVITY])[0] == Translation(
            "General trading", "glossary"
        )

    def test_a_spelling_variant_still_matches(self) -> None:
        """Vowel marks and a different alef are the same word to a reader, so also to us."""
        marked = ARABIC_ACTIVITY.replace("ت", "تَ", 1)
        assert GlossaryTranslator().translate([marked])[0].text == "General trading"

    def test_two_known_terms_with_a_separator(self) -> None:
        value = f"{ARABIC_LLC} - {ARABIC_ACTIVITY}"
        assert GlossaryTranslator().translate([value])[0].text == "LLC - General trading"

    def test_an_unknown_phrase_is_not_guessed(self) -> None:
        """A dictionary that invents an answer is worse than one that says it does not know."""
        result = GlossaryTranslator().translate([ARABIC_NAME])[0]
        assert result.text is None
        assert result.source == "none"


class TestTheBackendChoice:
    def test_demo_mode_uses_the_glossary_and_loads_no_azure_sdk(self) -> None:
        translation.reset_translator()
        assert isinstance(translation.get_translator(), GlossaryTranslator)

    def test_a_backend_failure_costs_a_reading_aid_not_a_case(self, monkeypatch) -> None:
        class Broken(TranslatorBackend):
            name = "broken"

            def translate(self, values: list[str]) -> list[Translation]:
                raise RuntimeError("model timed out")

        monkeypatch.setattr(translation, "_backend", Broken())
        results = translate_values([ARABIC_ACTIVITY, "CN-1042288"])
        assert [item.text for item in results] == [None, None]
        assert [item.source for item in results] == ["none", "none"]
        translation.reset_translator()

    def test_positions_are_preserved_so_a_reading_lands_on_its_own_field(self) -> None:
        values = ["CN-1042288", ARABIC_ACTIVITY, "2027-03-15", ARABIC_LLC]
        results = translate_values(values)
        assert [item.text for item in results] == [None, "General trading", None, "LLC"]


class TestTheModelBackend:
    """The Foundry translator, driven by a fake client: no network, real parsing."""

    @pytest.fixture(autouse=True)
    def _deployment(self, monkeypatch) -> None:
        """A deployment name, so the translator builds. No network is touched either way."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "azure_openai_deployment", "gpt-4.1-mini")

    def _translator(self, payload: str):
        from app.azure.foundry import FoundryTranslator
        from tests.test_azure import _Choice, _Response  # the same fakes the extractor uses

        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def client(self):
                outer = self

                class Chat:
                    class completions:
                        @staticmethod
                        def create(**kwargs):
                            outer.calls += 1
                            outer.last = kwargs
                            return _Response(_Choice(payload))

                return type("C", (), {"chat": Chat})()

        fake = FakeClient()
        return FoundryTranslator(client=fake), fake

    def test_one_call_translates_the_whole_list(self) -> None:
        payload = (
            '{"translations": [{"index": 0, "english": "General trading"}, '
            '{"index": 1, "english": "LLC"}]}'
        )
        translator, fake = self._translator(payload)
        results = translator.translate([ARABIC_ACTIVITY, ARABIC_LLC])

        assert [item.text for item in results] == ["General trading", "LLC"]
        assert all(item.source == "model" for item in results)
        assert fake.calls == 1, "one call per document, not one per field"

    def test_an_answer_is_matched_by_index_not_by_position(self) -> None:
        """A model that drops an item must not shift every later translation onto the wrong
        field — which is exactly what zipping by position would do."""
        payload = '{"translations": [{"index": 1, "english": "LLC"}]}'
        translator, _ = self._translator(payload)
        results = translator.translate([ARABIC_ACTIVITY, ARABIC_LLC])

        assert results[0].text is None
        assert results[1].text == "LLC"

    def test_a_null_answer_is_no_translation_rather_than_the_word_none(self) -> None:
        payload = '{"translations": [{"index": 0, "english": null}]}'
        translator, _ = self._translator(payload)
        assert translator.translate([ARABIC_NAME])[0] == Translation(None, "none")


class TestWhatReachesTheScreen:
    async def test_the_api_carries_the_reading_beside_the_untouched_value(
        self, client, auth, db_session
    ) -> None:
        """The screen gets both, and the value is exactly what the document said."""
        from sqlalchemy import select

        from app.db import models

        case = (
            await db_session.execute(select(models.Case).limit(1))
        ).scalars().first()
        db_session.add(
            models.ExtractedField(
                case_id=case.id,
                name="business_activity",
                label_en="Business activity",
                label_ar="النشاط التجاري",
                value=ARABIC_ACTIVITY,
                value_translated="General trading",
                translation_source="glossary",
                confidence=0.95,
                calibrated_confidence=0.95,
            )
        )
        await db_session.commit()

        response = await client.get(
            f"/api/v1/cases/{case.id}", headers=await auth("ops_officer")
        )
        assert response.status_code == 200
        field = next(
            f for f in response.json()["fields"] if f["name"] == "business_activity"
        )
        assert field["value"] == ARABIC_ACTIVITY, "the evidence is the document's own words"
        assert field["value_translated"] == "General trading"
        assert field["translation_source"] == "glossary"
