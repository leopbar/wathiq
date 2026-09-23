"""Use case 2 — salary certificates — added by configuration.

These tests prove the claim in three parts:

* the **profiles** are what the engine reads, and every case type has one;
* a salary case is **posted as an income verification** to a person's file, with its own
  idempotency key, while a KYC case still posts exactly as it did before profiles existed;
* the **employer** named on a certificate is checked against the registry, because the
  profile says so, and a missing or non-trading employer sends the case to a person.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent import investigator
from app.agent.tools import NODE_TOOLS, ToolBroker
from app.casetypes import load_profiles, profile_for
from app.db import models
from app.db.enums import CaseStatus, CaseType, DocTypeKey, Priority
from app.services import posting


class TestProfiles:
    def test_every_case_type_has_a_profile(self) -> None:
        """A case type without one would have nowhere to post; that must fail here, not live."""
        assert set(load_profiles()) == {case_type.value for case_type in CaseType}

    def test_an_unknown_case_type_has_no_default_destination(self) -> None:
        with pytest.raises(KeyError):
            profile_for("mortgage_application")

    def test_the_posting_tool_of_every_profile_is_allowed_to_the_posting_step(self) -> None:
        """The profile names a tool; least privilege must already permit exactly that tool."""
        for profile in load_profiles().values():
            assert profile.posting_tool in NODE_TOOLS["post"]["core_banking"]

    def test_kyc_keys_are_unchanged_by_the_move_to_profiles(self) -> None:
        """Keys issued before M7 must still match, or a retry of an old case posts twice."""
        assert profile_for("kyc_refresh").posting_record == "kyc_refresh"

    def test_salary_certificates_go_to_a_persons_file(self) -> None:
        profile = profile_for("salary_certificate")
        assert profile.customer_kind == "individual"
        assert profile.posting_tool == "post_income_verification"
        assert profile.expected_documents == ["salary_certificate"]


class TestTheEmployerCheck:
    def test_the_profile_adds_the_question_not_the_code(self) -> None:
        values = {"salary_certificate": {"employer_name": "Oasis Medical Supplies"}}
        with_profile = investigator.plan(values, profile_for("salary_certificate"))
        without_profile = investigator.plan(values, profile_for("kyc_refresh"))
        assert [q.kind for q in with_profile].count("registry_check") == 1
        assert "registry_check" not in [q.kind for q in without_profile]

    def test_a_certificate_with_no_employer_asks_nothing_about_one(self) -> None:
        questions = investigator.plan(
            {"salary_certificate": {"employer_name": None}}, profile_for("salary_certificate")
        )
        assert "registry_check" not in [q.kind for q in questions]

    async def _investigate(self, employer: str) -> investigator.Outcome:
        questions = investigator.plan(
            {"salary_certificate": {"employer_name": employer}},
            profile_for("salary_certificate"),
        )
        return await investigator.investigate(questions, ToolBroker.for_node("investigator"))

    async def test_a_trading_employer_raises_nothing(self) -> None:
        outcome = await self._investigate("Oasis Medical Supplies")
        step = next(s for s in outcome.steps if s.action == "company_registry.verify_employer")
        assert step.ok and "active" in step.observation
        assert not [f for f in outcome.findings if f["code"].startswith("EMPLOYER_")]

    async def test_a_suspended_employer_goes_to_a_person(self) -> None:
        outcome = await self._investigate("Sahara Green Contracting")
        assert [f["code"] for f in outcome.findings] == ["EMPLOYER_NOT_ACTIVE"]
        assert outcome.review_reasons[0]["code"] == "EMPLOYER_NOT_VERIFIED"

    async def test_an_unregistered_employer_goes_to_a_person(self) -> None:
        outcome = await self._investigate("Imaginary Widgets Company")
        assert [f["code"] for f in outcome.findings] == ["EMPLOYER_NOT_REGISTERED"]
        assert outcome.findings[0]["policy_citation"] == "LEN-POL-002 §1.2"


async def _salary_case(db, *, customer: str, fields: dict[str, str]) -> models.Case:
    case = models.Case(
        reference=f"WTQ-TEST-{uuid4().hex[:8]}",
        case_type=CaseType.salary_certificate,
        customer_name=customer,
        status=CaseStatus.approved,
        priority=Priority.normal,
        thread_id=uuid4().hex,
        straight_through=True,
    )
    db.add(case)
    await db.flush()
    document = models.Document(
        case_id=case.id,
        filename="salary.pdf",
        doc_type=DocTypeKey.salary_certificate,
        mime_type="application/pdf",
        size_bytes=1,
        storage_path=f"{case.id}/salary.pdf",
    )
    db.add(document)
    await db.flush()
    for name, value in fields.items():
        db.add(
            models.ExtractedField(
                case_id=case.id,
                document_id=document.id,
                name=name,
                label_en=name,
                value=value,
                confidence=0.95,
            )
        )
    await db.commit()
    return case


class TestIncomePosting:
    async def test_a_salary_case_posts_an_income_verification(self, db_session) -> None:
        case = await _salary_case(
            db_session,
            customer="Mariam Al Hashimi",
            fields={"employer_name": "Oasis Medical Supplies", "total_salary": "AED 26,400"},
        )
        result = await posting.post_case(case.id)

        assert result["status"] == "posted", result
        assert result["reference"].startswith("SIM-INC-")
        assert result["customer_id"] == "SIM-CUS-200001"
        assert ":income_verification:" in posting.idempotency_key(case)

    async def test_an_income_with_no_total_salary_is_not_sent(self, db_session) -> None:
        """Refused by us first, with a reason, rather than by the system of record."""
        case = await _salary_case(
            db_session,
            customer="Priya Nair",
            fields={"employer_name": "Oasis Medical Supplies", "total_salary": ""},
        )
        result = await posting.post_case(case.id)

        assert result["status"] == "skipped"
        assert "total_salary" in result["note"]

    async def test_a_salary_case_for_a_company_is_refused_by_the_system_of_record(
        self, db_session
    ) -> None:
        """The customer lookup finds a company; the core banking server will not write an
        income onto a company's file, and the refusal is recorded, not hidden."""
        case = await _salary_case(
            db_session,
            customer="Falcon Ridge Trading LLC",
            fields={"employer_name": "Oasis Medical Supplies", "total_salary": "AED 26,400"},
        )
        result = await posting.post_case(case.id)

        assert result["status"] == "failed"
        assert "Corporate" in result["note"]


class TestTheIntakeScreenSource:
    async def test_the_profiles_are_served_with_their_documents(
        self, client, auth
    ) -> None:
        response = await client.get(
            "/api/v1/system/case-types", headers=await auth("ops_officer")
        )
        assert response.status_code == 200
        salary = next(p for p in response.json() if p["id"] == "salary_certificate")
        assert [d["key"] for d in salary["expected_documents"]] == ["salary_certificate"]
        assert salary["expected_documents"][0]["label_ar"] == "شهادة راتب"
        assert salary["registry_checks"] == ["salary_certificate.employer_name"]

    async def test_the_profiles_need_a_signed_in_user(self, client) -> None:
        response = await client.get("/api/v1/system/case-types")
        assert response.status_code == 401
