"""The four MCP servers, driven in-process through the official MCP client.

`Client(server)` connects to an `MCPServer` object without a network, so these tests exercise
the real tool definitions, the real schemas and the real handlers — the same code path a
remote caller takes, minus the HTTP.

They live beside the servers rather than in the backend suite because these are a separate
service with their own image and their own dependencies. The backend's own tests cover the
*client* side: the allowlist, the call record and what happens when a server cannot be
reached.
"""

from __future__ import annotations

import pytest
from mcp import Client

from wathiq_mcp import company_registry, core_banking, data, document_store, sanctions

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def call(server, tool: str, /, **arguments) -> dict:
    """Call one tool on a server. Positional-only, so a tool argument named `name` or
    `server` does not collide with this helper's own parameters."""
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments)
    assert not result.is_error, result
    return dict(result.structured_content or {})


async def tool_names(server) -> set[str]:
    async with Client(server) as client:
        return {tool.name for tool in (await client.list_tools()).tools}


class TestNameMatching:
    def test_a_legal_form_difference_is_not_a_different_company(self) -> None:
        assert data.similarity("Al Noor Logistics LLC", "Al Noor Logistics L.L.C.") > 0.9

    def test_a_transliteration_difference_is_still_a_close_name(self) -> None:
        """Token overlap alone scores this 0.33 and would miss the match entirely."""
        assert data.similarity("Youssef Karam", "Youssef Karem") > 0.8

    def test_two_unrelated_names_are_not_similar(self) -> None:
        assert data.similarity("Falcon Ridge Trading", "Zenith Cloud Services") < 0.5


class TestCompanyRegistry:
    async def test_a_licence_is_found(self) -> None:
        answer = await call(
            company_registry.server, "lookup_by_license", license_number="CN-1042288"
        )
        assert answer["found"] is True
        assert answer["company"]["registered_name"] == "Falcon Ridge Trading LLC"

    async def test_an_unknown_licence_says_so_rather_than_guessing(self) -> None:
        answer = await call(
            company_registry.server, "lookup_by_license", license_number="CN-0000000"
        )
        assert answer["found"] is False

    async def test_it_reconciles_two_spellings_of_one_company(self) -> None:
        answer = await call(
            company_registry.server,
            "reconcile_names",
            name_a="Al Noor Logistics LLC",
            name_b="Al Noor Logistics FZ-LLC",
        )
        assert answer["same_company"] is True
        assert answer["registered_name"] == "Al Noor Logistics FZ-LLC"

    async def test_two_different_companies_are_not_reconciled(self) -> None:
        answer = await call(
            company_registry.server,
            "reconcile_names",
            name_a="Falcon Ridge Trading LLC",
            name_b="Zenith Cloud Services",
        )
        assert answer["same_company"] is False

    async def test_it_reports_a_company_that_is_not_trading(self) -> None:
        answer = await call(
            company_registry.server, "lookup_by_license", license_number="CN-5529114"
        )
        assert answer["company"]["status"] == "suspended"

    async def test_every_answer_is_labelled_simulated(self) -> None:
        answer = await call(company_registry.server, "search_by_name", name="Falcon")
        assert answer["simulated"] is True
        assert all(match["simulated"] for match in answer["matches"])

    async def test_it_exposes_no_tool_that_writes(self) -> None:
        names = await tool_names(company_registry.server)
        assert names == {"lookup_by_license", "search_by_name", "reconcile_names"}


class TestSanctions:
    async def test_a_transliterated_near_miss_is_a_possible_match(self) -> None:
        answer = await call(sanctions.server, "screen_name", name="Youssef Karam")
        assert answer["band"] in {"possible", "strong"}
        assert answer["requires_human_decision"] is True

    async def test_an_unrelated_name_is_clear(self) -> None:
        answer = await call(sanctions.server, "screen_name", name="Hamad Al Suwaidi")
        assert answer["band"] == "none"
        assert answer["requires_human_decision"] is False

    async def test_it_returns_candidates_and_never_a_verdict(self) -> None:
        """Deciding what a possible match means is a human's job, by design."""
        answer = await call(sanctions.server, "screen_name", name="Youssef Karam")
        assert "decision" not in answer
        assert "approved" not in answer

    async def test_every_answer_says_the_list_is_invented(self) -> None:
        answer = await call(sanctions.server, "screen_name", name="anyone at all")
        assert answer["simulated"] is True
        assert "SIMULATED" in answer["source"]

    async def test_the_list_describes_itself_honestly(self) -> None:
        answer = await call(sanctions.server, "describe_list")
        assert answer["entry_count"] == len(data.SANCTIONS)
        assert answer["simulated"] is True


class TestCoreBanking:
    async def test_a_customer_is_found_by_name(self) -> None:
        answer = await call(core_banking.server, "get_customer", name="Falcon Ridge Trading LLC")
        assert answer["found"] is True
        assert answer["customer"]["simulated"] is True

    async def test_a_post_without_an_approver_is_refused(self) -> None:
        """A pipeline may not post something no human signed off."""
        answer = await call(
            core_banking.server,
            "post_kyc_refresh",
            case_id="c1",
            customer_id="SIM-CUS-100001",
            idempotency_key="k1",
            approved_by="",
        )
        assert answer["posted"] is False
        assert "approved_by" in answer["error"]

    async def test_a_post_without_an_idempotency_key_is_refused(self) -> None:
        answer = await call(
            core_banking.server,
            "post_kyc_refresh",
            case_id="c1",
            customer_id="SIM-CUS-100001",
            idempotency_key="",
            approved_by="Layla Haddad",
        )
        assert answer["posted"] is False
        assert "idempotency_key" in answer["error"]

    async def test_the_same_key_twice_posts_once(self) -> None:
        """The retry case: a timeout, a redelivery or a crash must not post twice."""
        first = await call(
            core_banking.server,
            "post_kyc_refresh",
            case_id="c1",
            customer_id="SIM-CUS-100001",
            idempotency_key="idem-1",
            approved_by="Layla Haddad",
        )
        second = await call(
            core_banking.server,
            "post_kyc_refresh",
            case_id="c1",
            customer_id="SIM-CUS-100001",
            idempotency_key="idem-1",
            approved_by="Layla Haddad",
        )
        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert first["reference"] == second["reference"]

    async def test_an_unknown_kind_of_approval_is_refused(self) -> None:
        """The authority behind a posting is part of the record, so it cannot be invented."""
        answer = await call(
            core_banking.server,
            "post_kyc_refresh",
            case_id="c3",
            customer_id="SIM-CUS-100001",
            idempotency_key="idem-kind",
            approved_by="Someone",
            approval_kind="because_i_said_so",
        )
        assert answer["posted"] is False
        assert "approval_kind" in answer["error"]

    async def test_a_policy_approval_is_accepted_and_recorded_as_one(self) -> None:
        """A case no person looked at is posted under a named policy, and says which."""
        answer = await call(
            core_banking.server,
            "post_kyc_refresh",
            case_id="c4",
            customer_id="SIM-CUS-100001",
            idempotency_key="idem-policy",
            approved_by="Straight-through policy STP-001",
            approval_kind="straight_through_policy",
        )
        assert answer["posted"] is True
        assert answer["approval_kind"] == "straight_through_policy"
        read = await call(core_banking.server, "get_posting", reference=answer["reference"])
        assert read["posting"]["approval_kind"] == "straight_through_policy"

    async def test_a_posting_can_be_read_back(self) -> None:
        posted = await call(
            core_banking.server,
            "post_kyc_refresh",
            case_id="c2",
            customer_id="SIM-CUS-100002",
            idempotency_key="idem-2",
            approved_by="Layla Haddad",
        )
        read = await call(core_banking.server, "get_posting", reference=posted["reference"])
        assert read["found"] is True
        assert read["posting"]["case_id"] == "c2"


class TestDocumentStore:
    async def test_a_path_outside_the_storage_root_is_refused(self) -> None:
        """A tool that takes a path from a model has to assume the path is hostile."""
        answer = await call(document_store.server, "read_document", path="../../etc/passwd")
        assert answer["found"] is False
        assert "outside" in answer["error"]

    async def test_an_absolute_path_is_refused(self) -> None:
        answer = await call(document_store.server, "read_document", path="/etc/passwd")
        assert answer["found"] is False

    async def test_a_missing_document_says_so(self) -> None:
        answer = await call(document_store.server, "read_document", path="nope/missing.pdf")
        assert answer["found"] is False
        assert answer["error"] == "no such document"

    async def test_it_exposes_no_tool_that_writes(self) -> None:
        names = await tool_names(document_store.server)
        assert names == {"list_case_documents", "read_document", "find_in_document"}
        assert not any(
            word in name for name in names for word in ("write", "delete", "save", "update")
        )
