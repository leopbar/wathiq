"""Integration tests: real database, real HTTP through the ASGI app."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.pdf import simple_pdf

pytestmark = pytest.mark.asyncio


class TestHealthAndMode:
    async def test_healthz(self, client: AsyncClient) -> None:
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["db"] == "ok"

    async def test_mode_needs_no_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/settings/mode")
        assert response.status_code == 200
        assert response.json()["mode"] == "demo"


class TestAuth:
    async def test_demo_users_listed(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/demo-users")
        assert response.status_code == 200
        roles = {user["role"] for user in response.json()}
        assert roles == {"ops_officer", "reviewer", "supervisor", "admin", "auditor"}

    async def test_demo_login_returns_a_working_token(self, client: AsyncClient, auth) -> None:
        headers = await auth("reviewer")
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["role"] == "reviewer"

    async def test_password_login(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "omar.haddad@wathiq.demo", "password": "Wathiq!Demo2026"},
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "reviewer"

    async def test_wrong_password_is_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "omar.haddad@wathiq.demo", "password": "nope"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"

    async def test_unknown_email_is_rejected_the_same_way(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": "ghost@wathiq.demo", "password": "nope"}
        )
        assert response.status_code == 401

    async def test_no_token_is_unauthorized(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/cases")).status_code == 401

    async def test_garbage_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/cases", headers={"Authorization": "Bearer not.a.token"}
        )
        assert response.status_code == 401


class TestRoleGating:
    async def test_reviewer_cannot_list_users(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/settings/users", headers=await auth("reviewer"))
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    async def test_admin_can_list_users(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/settings/users", headers=await auth("admin"))
        assert response.status_code == 200
        assert len(response.json()) == 5

    async def test_auditor_cannot_create_a_case(self, client: AsyncClient, auth) -> None:
        response = await client.post(
            "/api/v1/cases",
            json={"customer_name": "Test Co", "case_type": "kyc_refresh"},
            headers=await auth("auditor"),
        )
        assert response.status_code == 403

    async def test_ops_officer_cannot_open_the_review_queue(
        self, client: AsyncClient, auth
    ) -> None:
        response = await client.get("/api/v1/review/queue", headers=await auth("ops_officer"))
        assert response.status_code == 403


class TestCases:
    async def test_list_is_paginated(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/cases?size=5", headers=await auth("reviewer"))
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 30
        assert len(body["items"]) == 5
        assert body["pages"] == 6

    async def test_status_filter(self, client: AsyncClient, auth) -> None:
        response = await client.get(
            "/api/v1/cases?status=needs_review", headers=await auth("reviewer")
        )
        assert response.status_code == 200
        assert {item["status"] for item in response.json()["items"]} == {"needs_review"}

    async def test_search_by_reference(self, client: AsyncClient, auth) -> None:
        headers = await auth("reviewer")
        first = (await client.get("/api/v1/cases?size=1", headers=headers)).json()["items"][0]
        response = await client.get(f"/api/v1/cases?q={first['reference']}", headers=headers)
        assert response.json()["total"] == 1

    async def test_detail_carries_the_whole_case(self, client: AsyncClient, auth) -> None:
        headers = await auth("reviewer")
        listed = (await client.get("/api/v1/cases?size=1", headers=headers)).json()["items"][0]
        response = await client.get(f"/api/v1/cases/{listed['id']}", headers=headers)
        assert response.status_code == 200
        detail = response.json()
        assert detail["documents"] and detail["fields"] and detail["timeline"]
        assert detail["thread_id"]
        # Every field carries its own confidence and grounding.
        assert all("calibrated_confidence" in field for field in detail["fields"])

    async def test_unknown_case_is_404(self, client: AsyncClient, auth) -> None:
        response = await client.get(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000",
            headers=await auth("reviewer"),
        )
        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"


class TestCaseLifecycle:
    async def test_create_upload_and_start(self, client: AsyncClient, auth) -> None:
        headers = await auth("ops_officer")

        created = await client.post(
            "/api/v1/cases",
            json={
                "customer_name": "Test Harbour Trading LLC",
                "customer_name_ar": "اختبار",
                "case_type": "kyc_refresh",
                "priority": "high",
            },
            headers=headers,
        )
        assert created.status_code == 201
        case = created.json()
        assert case["status"] == "intake"
        assert case["reference"].startswith("WTQ-")

        pdf = simple_pdf("Trade licence", [("Licence number", "CN-7654321")], "test")
        uploaded = await client.post(
            f"/api/v1/cases/{case['id']}/documents",
            files=[("files", ("licence.pdf", pdf, "application/pdf"))],
            headers=headers,
        )
        assert uploaded.status_code == 201
        assert uploaded.json()[0]["filename"] == "licence.pdf"

        started = await client.post(f"/api/v1/cases/{case['id']}/start", headers=headers)
        assert started.status_code == 200
        assert started.json()["status"] == "processing"

        detail = (await client.get(f"/api/v1/cases/{case['id']}", headers=headers)).json()
        actions = [event["action"] for event in detail["timeline"]]
        assert "case.created" in actions
        assert "documents.uploaded" in actions

    async def test_start_without_documents_is_refused(self, client: AsyncClient, auth) -> None:
        headers = await auth("ops_officer")
        case = (
            await client.post(
                "/api/v1/cases",
                json={"customer_name": "Empty Case LLC", "case_type": "kyc_refresh"},
                headers=headers,
            )
        ).json()
        response = await client.post(f"/api/v1/cases/{case['id']}/start", headers=headers)
        assert response.status_code == 422
        assert response.json()["code"] == "NO_DOCUMENTS"

    async def test_unsupported_file_type_is_refused(self, client: AsyncClient, auth) -> None:
        headers = await auth("ops_officer")
        case = (
            await client.post(
                "/api/v1/cases",
                json={"customer_name": "Bad Upload LLC", "case_type": "kyc_refresh"},
                headers=headers,
            )
        ).json()
        response = await client.post(
            f"/api/v1/cases/{case['id']}/documents",
            files=[("files", ("notes.txt", b"hello", "text/plain"))],
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"

    async def test_document_bytes_are_served_back(self, client: AsyncClient, auth) -> None:
        headers = await auth("reviewer")
        listed = (await client.get("/api/v1/cases?size=50", headers=headers)).json()["items"]
        with_documents = next(item for item in listed if item["document_count"] > 0)
        detail = (
            await client.get(f"/api/v1/cases/{with_documents['id']}", headers=headers)
        ).json()
        document = detail["documents"][0]
        response = await client.get(document["preview_url"], headers=headers)
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")


class TestBrowserAuth:
    """`?token=` is accepted on exactly the three GETs the browser must make by itself."""

    async def test_document_preview_accepts_a_query_token(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("reviewer")
        token = headers["Authorization"].removeprefix("Bearer ")
        listed = (await client.get("/api/v1/cases?size=50", headers=headers)).json()["items"]
        with_documents = next(item for item in listed if item["document_count"] > 0)
        detail = (
            await client.get(f"/api/v1/cases/{with_documents['id']}", headers=headers)
        ).json()
        url = detail["documents"][0]["preview_url"]

        assert (await client.get(url)).status_code == 401
        assert (await client.get(f"{url}?token={token}")).status_code == 200

    async def test_audit_export_accepts_a_query_token(self, client: AsyncClient, auth) -> None:
        token = (await auth("auditor"))["Authorization"].removeprefix("Bearer ")
        assert (await client.get("/api/v1/audit/export")).status_code == 401
        response = await client.get(f"/api/v1/audit/export?token={token}")
        assert response.status_code == 200

    async def test_a_bad_query_token_is_rejected(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/audit/export?token=not-a-token")
        assert response.status_code == 401

    async def test_event_stream_requires_authentication(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("reviewer")
        case = (await client.get("/api/v1/cases?size=1", headers=headers)).json()["items"][0]
        assert (await client.get(f"/api/v1/cases/{case['id']}/events")).status_code == 401

    async def test_write_endpoints_ignore_a_query_token(self, client: AsyncClient, auth) -> None:
        """A token in the URL must never be enough to change anything."""
        token = (await auth("ops_officer"))["Authorization"].removeprefix("Bearer ")
        response = await client.post(
            f"/api/v1/cases?token={token}",
            json={"customer_name": "Query Token Co", "case_type": "kyc_refresh"},
        )
        assert response.status_code == 401


class TestReview:
    async def test_queue_lists_open_work(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/review/queue", headers=await auth("reviewer"))
        assert response.status_code == 200
        items = response.json()["items"]
        assert items
        assert all(item["status"] != "completed" for item in items)
        valid_sla = {"on_track", "at_risk", "breached", "none"}
        assert all(item["sla_state"] in valid_sla for item in items)

    async def test_claim_then_approve(self, client: AsyncClient, auth) -> None:
        headers = await auth("reviewer")
        queue = (await client.get("/api/v1/review/queue", headers=headers)).json()["items"]
        task = next(item for item in queue if item["status"] == "pending")

        claimed = await client.post(f"/api/v1/review/tasks/{task['id']}/claim", headers=headers)
        assert claimed.status_code == 200
        assert claimed.json()["status"] == "in_progress"

        decided = await client.post(
            f"/api/v1/review/tasks/{task['id']}/decision",
            json={"decision": "approve", "reason_code": "VALUES_CONFIRMED"},
            headers=headers,
        )
        assert decided.status_code == 200
        assert decided.json()["decision"] == "approve"

        case = (await client.get(f"/api/v1/cases/{task['case_id']}", headers=headers)).json()
        assert case["status"] == "approved"
        assert all(finding["status"] != "open" for finding in case["findings"])

    async def test_correction_is_recorded_on_the_field(self, client: AsyncClient, auth) -> None:
        headers = await auth("reviewer")
        queue = (await client.get("/api/v1/review/queue", headers=headers)).json()["items"]
        task = next(item for item in queue if item["status"] == "pending")
        detail = (await client.get(f"/api/v1/review/tasks/{task['id']}", headers=headers)).json()
        field = detail["case"]["fields"][0]

        decided = await client.post(
            f"/api/v1/review/tasks/{task['id']}/decision",
            json={
                "decision": "correct",
                "reason_code": "OCR_ERROR",
                "note": "Digit misread",
                "field_corrections": [{"field_id": field["id"], "value": "CORRECTED-VALUE"}],
            },
            headers=headers,
        )
        assert decided.status_code == 200

        case = (await client.get(f"/api/v1/cases/{task['case_id']}", headers=headers)).json()
        corrected = next(f for f in case["fields"] if f["id"] == field["id"])
        assert corrected["corrected_value"] == "CORRECTED-VALUE"
        assert corrected["status"] == "corrected"

    async def test_correct_without_corrections_is_refused(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("reviewer")
        queue = (await client.get("/api/v1/review/queue", headers=headers)).json()["items"]
        task = next(item for item in queue if item["status"] == "pending")
        response = await client.post(
            f"/api/v1/review/tasks/{task['id']}/decision",
            json={"decision": "correct"},
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "NO_CORRECTIONS"

    async def test_reason_codes_are_offered(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/review/reason-codes", headers=await auth("reviewer"))
        assert response.status_code == 200
        codes = {item["code"] for item in response.json()}
        assert "OCR_ERROR" in codes and "POSSIBLE_SANCTIONS_HIT" in codes


class TestDashboard:
    async def test_kpis(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/dashboard/kpis", headers=await auth("supervisor"))
        assert response.status_code == 200
        body = response.json()
        assert body["cases_total"] >= 30
        assert 0 <= body["straight_through_rate"] <= 1
        assert 0 <= body["review_rate"] <= 1

    async def test_charts_have_every_series(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/dashboard/charts", headers=await auth("supervisor"))
        assert response.status_code == 200
        body = response.json()
        assert body["volume_by_day"] and body["status_split"]
        assert len(body["confidence_histogram"]) == 6


class TestQualityAndPrompts:
    async def test_summary_covers_five_bands(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/quality/summary", headers=await auth("reviewer"))
        assert response.status_code == 200
        bands = {band["band"] for band in response.json()["bands"]}
        assert bands == {"model", "prompt", "agent", "ai_security", "adversarial"}

    async def test_calibration_reports_ece(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/quality/calibration", headers=await auth("reviewer"))
        assert response.status_code == 200
        body = response.json()
        assert body["points"]
        assert 0 <= body["ece"] <= 1

    async def test_prompt_versions_are_semver_ordered(self, client: AsyncClient, auth) -> None:
        headers = await auth("admin")
        response = await client.get(
            "/api/v1/prompts/extract_trade_license/versions", headers=headers
        )
        assert response.status_code == 200
        versions = [v["version"] for v in response.json()]
        assert versions == ["2.1.0", "2.0.0", "1.0.0"]

    async def test_diff_between_versions(self, client: AsyncClient, auth) -> None:
        response = await client.get(
            "/api/v1/prompts/extract_trade_license/diff?from=2.0.0&to=2.1.0",
            headers=await auth("admin"),
        )
        assert response.status_code == 200
        assert "+++" in response.json()["unified_diff"]

    async def test_only_admin_approves_a_version(self, client: AsyncClient, auth) -> None:
        path = "/api/v1/prompts/investigate_mismatch/versions/0.9.0/approve"
        assert (await client.post(path, headers=await auth("reviewer"))).status_code == 403

        approved = await client.post(path, headers=await auth("admin"))
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["approved_by"]


class TestAuditAndSystem:
    async def test_audit_is_searchable(self, client: AsyncClient, auth) -> None:
        response = await client.get(
            "/api/v1/audit?q=created&size=5", headers=await auth("auditor")
        )
        assert response.status_code == 200
        assert response.json()["items"]

    async def test_audit_exports_csv(self, client: AsyncClient, auth) -> None:
        response = await client.get("/api/v1/audit/export", headers=await auth("auditor"))
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert response.text.splitlines()[0].startswith("timestamp,case_reference")

    async def test_system_info_is_honest_about_simulated_services(
        self, client: AsyncClient, auth
    ) -> None:
        response = await client.get("/api/v1/system/info", headers=await auth("auditor"))
        assert response.status_code == 200
        body = response.json()
        assert {d["key"] for d in body["diagrams"]} >= {"system", "layers", "graph"}
        simulated = [s for s in body["services"] if s["detail"].startswith("SIMULATED")]
        assert len(simulated) >= 3

    async def test_integrations_label_simulated_services(self, client: AsyncClient, auth) -> None:
        response = await client.get(
            "/api/v1/settings/integrations", headers=await auth("auditor")
        )
        statuses = {item["key"]: item["status"] for item in response.json()}
        assert statuses["core_banking"] == "simulated"
        assert statuses["sanctions"] == "simulated"
