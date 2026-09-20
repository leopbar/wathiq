"""Tests for the process layer.

Four things are worth testing here, and they are the four things that would hurt in production:

* the **definition** the engines execute really is the one the code describes;
* **posting** happens once, only after an approval, and never silently not at all;
* **escalation** happens once, and does not take work away from someone mid-decision;
* the **audit trail** cannot be rewritten, and a crash does not lose a case.

The Conductor engine is tested against a fake HTTP transport rather than a running server, so
these tests say something definite in CI without 2 GB of Java.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.agent import runner
from app.db import models
from app.db.enums import (
    CaseStatus,
    CaseType,
    PostingStatus,
    Priority,
    ReviewDecision,
    ReviewReason,
    ReviewStatus,
    Role,
)
from app.db.session import engine as db_engine
from app.process import base, definition
from app.process.conductor import ConductorEngine
from app.process.conductor_client import ConductorClient
from app.process.inprocess import InProcessEngine
from app.process.worker import HANDLERS, missing_handlers
from app.services import audit_trail, escalation, pipeline, posting
from app.services.pdf import simple_pdf

# ---------------------------------------------------------------- the definition


class TestTheDefinition:
    """The workflow JSON, the step list and the diagram all come from one file. Prove it."""

    def _refs(self, tasks: list[dict], seen: set[str]) -> set[str]:
        """Every task reference name in the workflow, including the nested branches."""
        for task in tasks:
            seen.add(task["taskReferenceName"])
            for branch in task.get("forkTasks", []):
                self._refs(branch, seen)
            for branch in (task.get("decisionCases") or {}).values():
                self._refs(branch, seen)
            self._refs(task.get("defaultCase") or [], seen)
        return seen

    def test_the_json_and_the_step_list_describe_the_same_steps(self) -> None:
        workflow = definition.workflow_definition()
        in_json = self._refs(workflow["tasks"], set())
        declared = {step.ref for step in definition.STEPS}
        # `review_and_timer` is the fork itself, which the step list represents as the two
        # things a reader cares about: the review and the timer beside it.
        assert in_json - {"review_and_timer"} == declared

    def test_every_worker_queue_has_a_handler(self) -> None:
        """A queue nobody polls would leave every case stuck at that step, with no error."""
        assert missing_handlers() == []
        assert set(definition.WORKER_QUEUES) <= set(HANDLERS)

    def test_the_route_is_decided_by_the_agent_and_nothing_else(self) -> None:
        switch = next(
            task
            for task in definition.workflow_definition()["tasks"]
            if task["taskReferenceName"] == "review_needed"
        )
        assert switch["inputParameters"]["route"] == "${agent.output.route}"
        assert set(switch["decisionCases"]) == {definition.ROUTE_REVIEW}
        # Straight-through is the default case: no human step at all, not a skipped one.
        assert switch["defaultCase"] == []

    def test_the_timer_runs_beside_the_review_and_the_join_waits_only_for_it(self) -> None:
        branch = next(
            task
            for task in definition.workflow_definition()["tasks"]
            if task["taskReferenceName"] == "review_needed"
        )["decisionCases"][definition.ROUTE_REVIEW]
        fork = branch[0]
        assert fork["type"] == "FORK_JOIN"
        assert [task["taskReferenceName"] for task in fork["forkTasks"][0]] == ["human_review"]
        assert [task["taskReferenceName"] for task in fork["forkTasks"][1]] == [
            "sla_timer",
            "sla_escalation",
        ]
        # The crucial line: a fired timer must never finish a case on a human's behalf.
        assert branch[1]["joinOn"] == ["human_review"]

    def test_exactly_one_step_writes_outside_wathiq(self) -> None:
        writers = [step.ref for step in definition.STEPS if step.writes_externally]
        assert writers == ["post"]

    def test_the_human_task_never_times_out(self) -> None:
        human = next(
            task
            for task in definition.task_definitions()
            if task["name"] == definition.HUMAN_QUEUE
        )
        assert human["timeoutSeconds"] == 0
        assert human["timeoutPolicy"] == "ALERT_ONLY"

    def test_the_payload_carries_no_customer_data(self) -> None:
        """Conductor is a separate system with its own retention: it gets an id, not a file."""
        body = json.dumps(definition.workflow_definition())
        assert "customer_name" not in body
        assert "ocr_text" not in body

    def test_the_diagram_is_generated_from_the_definition(self) -> None:
        drawing = definition.mermaid()
        assert "SLA timer" in drawing
        assert str(definition.mermaid().count("-->")) != "0"
        assert definition.describe()["workflow"] == definition.WORKFLOW_NAME


# --------------------------------------------------------------------- fixtures


async def _case(db, *, status: CaseStatus, straight_through: bool = False) -> models.Case:
    case = models.Case(
        reference=f"WTQ-TEST-{uuid4().hex[:8]}",
        case_type=CaseType.kyc_refresh,
        customer_name="Falcon Ridge Trading LLC",
        status=status,
        priority=Priority.normal,
        thread_id=uuid4().hex,
        straight_through=straight_through,
    )
    db.add(case)
    await db.flush()
    return case


async def _review_task(
    db,
    case: models.Case,
    *,
    status: ReviewStatus,
    due_at: datetime,
    decision: ReviewDecision | None = None,
    assigned_to_id=None,
) -> models.ReviewTask:
    task = models.ReviewTask(
        case_id=case.id,
        reason=ReviewReason.mandatory,
        reason_code="DOCUMENT_EXPIRED",
        reason_label="Document expired",
        status=status,
        assigned_role=Role.reviewer,
        assigned_to_id=assigned_to_id,
        sla_due_at=due_at,
        decision=decision,
        completed_at=datetime.now(UTC) if status == ReviewStatus.completed else None,
    )
    db.add(task)
    await db.flush()
    return task


# ----------------------------------------------------------------------- posting


class TestPosting:
    async def test_a_straight_through_case_is_posted_under_a_named_policy(
        self, db_session
    ) -> None:
        """Nobody looked at it, so the audit trail must name the policy — not a person."""
        case = await _case(db_session, status=CaseStatus.approved, straight_through=True)
        await db_session.commit()

        result = await posting.post_case(case.id)

        assert result["status"] == "posted"
        assert result["approval_kind"] == "straight_through_policy"
        assert result["approved_by"] == posting.STRAIGHT_THROUGH_AUTHORITY
        assert result["reference"].startswith("SIM-KYC-")

    async def test_a_reviewed_case_is_posted_under_the_reviewers_name(self, db_session) -> None:
        case = await _case(db_session, status=CaseStatus.approved)
        reviewer = (
            await db_session.execute(select(models.User).where(models.User.role == Role.reviewer))
        ).scalars().first()
        await _review_task(
            db_session,
            case,
            status=ReviewStatus.completed,
            due_at=datetime.now(UTC) + timedelta(hours=2),
            decision=ReviewDecision.approve,
            assigned_to_id=reviewer.id,
        )
        await db_session.commit()

        result = await posting.post_case(case.id)

        assert result["status"] == "posted"
        assert result["approval_kind"] == "human"
        assert result["approved_by"] == reviewer.full_name

    async def test_posting_twice_does_not_post_twice(self, db_session) -> None:
        """The heart of it: the same case always produces the same idempotency key."""
        case = await _case(db_session, status=CaseStatus.approved, straight_through=True)
        await db_session.commit()

        first = await posting.post_case(case.id)
        second = await posting.post_case(case.id)

        assert first["reference"] == second["reference"]
        rows = (
            await db_session.execute(
                select(models.Posting).where(models.Posting.case_id == case.id)
            )
        ).scalars().all()
        assert len(rows) == 1, "a second attempt must not write a second posting"

    async def test_the_key_is_derived_from_the_workflow_not_random(self, db_session) -> None:
        case = await _case(db_session, status=CaseStatus.approved, straight_through=True)
        await db_session.commit()
        assert posting.idempotency_key(case) == posting.idempotency_key(case)
        assert case.thread_id in posting.idempotency_key(case)

    async def test_a_rejected_case_is_not_posted_and_says_so(self, db_session) -> None:
        case = await _case(db_session, status=CaseStatus.rejected)
        await db_session.commit()

        result = await posting.post_case(case.id)

        assert result["status"] == "skipped"
        assert "rejected" in result["note"].lower()

    async def test_a_case_with_no_approval_is_not_posted(self, db_session) -> None:
        """No reviewer decision and not straight-through: nothing may reach the bank."""
        case = await _case(db_session, status=CaseStatus.approved, straight_through=False)
        await db_session.commit()

        result = await posting.post_case(case.id)

        assert result["status"] == "skipped"
        assert "approval" in result["note"].lower()

    async def test_an_unknown_customer_is_a_recorded_skip_not_a_silent_one(
        self, db_session
    ) -> None:
        case = await _case(db_session, status=CaseStatus.approved, straight_through=True)
        case.customer_name = "Nobody Of That Name Trading LLC"
        await db_session.commit()

        result = await posting.post_case(case.id)

        assert result["status"] == "skipped"
        assert "no customer matching" in result["note"].lower()
        row = await posting.for_case(db_session, case.id)
        assert row is not None and row.status == PostingStatus.skipped


# -------------------------------------------------------------------- escalation


class TestEscalation:
    async def test_an_overdue_unclaimed_review_moves_to_the_supervisor(self, db_session) -> None:
        case = await _case(db_session, status=CaseStatus.needs_review)
        task = await _review_task(
            db_session,
            case,
            status=ReviewStatus.pending,
            due_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        await db_session.commit()

        assert await escalation.escalate_overdue() >= 1

        await db_session.refresh(task)
        await db_session.refresh(case)
        assert task.escalated_at is not None
        assert task.assigned_role == Role.supervisor
        assert task.assigned_to_id is None
        assert case.priority == Priority.high
        # Still open: escalation asks someone else to decide, it does not decide.
        assert task.status == ReviewStatus.pending

    async def test_escalating_twice_changes_nothing_the_second_time(self, db_session) -> None:
        """A redelivered timer, or a sweep every minute, must not escalate again."""
        case = await _case(db_session, status=CaseStatus.needs_review)
        task = await _review_task(
            db_session,
            case,
            status=ReviewStatus.pending,
            due_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        await db_session.commit()

        await escalation.escalate_overdue()
        await db_session.refresh(task)
        first = task.escalated_at

        await escalation.escalate_overdue()
        await escalation.escalate_case(case.id)
        await db_session.refresh(task)

        assert task.escalated_at == first
        events = (
            await db_session.execute(
                select(models.Event).where(
                    models.Event.case_id == case.id,
                    models.Event.action == base.ESCALATED,
                )
            )
        ).scalars().all()
        assert len(events) == 1, "one escalation, one entry in the audit trail"

    async def test_a_review_somebody_is_working_on_stays_with_them(self, db_session) -> None:
        """Taking a half-made decision away from a person is worse than a late case."""
        case = await _case(db_session, status=CaseStatus.in_review)
        reviewer = (
            await db_session.execute(select(models.User).where(models.User.role == Role.reviewer))
        ).scalars().first()
        task = await _review_task(
            db_session,
            case,
            status=ReviewStatus.in_progress,
            due_at=datetime.now(UTC) - timedelta(minutes=10),
            assigned_to_id=reviewer.id,
        )
        await db_session.commit()

        await escalation.escalate_overdue()
        await db_session.refresh(task)

        assert task.escalated_at is not None
        assert task.assigned_to_id == reviewer.id
        assert task.assigned_role == Role.supervisor

    async def test_a_review_inside_its_sla_is_left_alone(self, db_session) -> None:
        case = await _case(db_session, status=CaseStatus.needs_review)
        task = await _review_task(
            db_session,
            case,
            status=ReviewStatus.pending,
            due_at=datetime.now(UTC) + timedelta(hours=3),
        )
        await db_session.commit()

        result = await escalation.escalate_case(case.id)
        await db_session.refresh(task)

        assert result["escalated"] == 0
        assert task.escalated_at is None
        assert task.assigned_role == Role.reviewer

    async def test_an_escalated_review_leaves_the_reviewers_queue(
        self, client: AsyncClient, auth, db_session
    ) -> None:
        case = await _case(db_session, status=CaseStatus.needs_review)
        task = await _review_task(
            db_session,
            case,
            status=ReviewStatus.pending,
            due_at=datetime.now(UTC) - timedelta(minutes=45),
        )
        await db_session.commit()

        reviewer = await auth("reviewer")
        before = (
            await client.get(
                "/api/v1/review/queue", headers=reviewer, params={"page": 1, "size": 100}
            )
        ).json()
        assert any(item["id"] == str(task.id) for item in before["items"])

        await escalation.escalate_overdue()

        after = (
            await client.get(
                "/api/v1/review/queue", headers=reviewer, params={"page": 1, "size": 100}
            )
        ).json()
        assert not any(item["id"] == str(task.id) for item in after["items"])

        supervisor = await auth("supervisor")
        theirs = (
            await client.get(
                "/api/v1/review/queue", headers=supervisor, params={"page": 1, "size": 100}
            )
        ).json()
        assert any(item["id"] == str(task.id) for item in theirs["items"])


# ------------------------------------------------------------------ audit trail


class TestTheAuditTrail:
    async def test_an_event_cannot_be_changed(self, db_session) -> None:
        """Append-only is a claim, so the database has to be the one enforcing it.

        Each attempt runs on its own connection: a statement the server rejects poisons the
        transaction it was sent on, and reusing that connection afterwards would fail for a
        reason that has nothing to do with what is being tested.
        """
        row = (await db_session.execute(select(models.Event).limit(1))).scalars().first()
        assert row is not None

        for statement in (
            "UPDATE events SET label = 'tampered' WHERE id = :id",
            "DELETE FROM events WHERE id = :id",
        ):
            async with db_engine.connect() as connection:
                with pytest.raises(Exception) as refused:
                    await connection.execute(text(statement), {"id": row.id})
            assert "append-only" in str(refused.value)

    async def test_the_integrity_check_reports_the_trigger(self, db_session) -> None:
        report = await audit_trail.verify(db_session)
        assert report["append_only_enforced"] is True
        assert report["rows"] > 0
        # It must also say what it does not prove.
        assert "superuser" in report["limits"]

    async def test_the_check_is_reachable_over_the_api(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("auditor")
        response = await client.get("/api/v1/process/audit-integrity", headers=headers)
        assert response.status_code == 200
        assert response.json()["append_only_enforced"] is True


# -------------------------------------------------------------------- recovery


class TestCrashRecovery:
    async def test_a_case_left_approved_by_a_crash_is_finished(self, db_session) -> None:
        """The graph finished, then the container died before posting. Recovery finishes it."""
        case = await _case(db_session, status=CaseStatus.approved, straight_through=True)
        await db_session.commit()

        recovered = await InProcessEngine().recover()
        await pipeline.drain(timeout=30.0)

        assert recovered >= 1
        await db_session.refresh(case)
        assert case.status == CaseStatus.completed
        row = await posting.for_case(db_session, case.id)
        assert row is not None and row.status == PostingStatus.posted

    async def test_recovery_says_so_in_the_audit_trail(self, db_session) -> None:
        case = await _case(db_session, status=CaseStatus.approved, straight_through=True)
        await db_session.commit()

        await InProcessEngine().recover()
        await pipeline.drain(timeout=30.0)

        actions = [
            row.action
            for row in (
                await db_session.execute(
                    select(models.Event).where(models.Event.case_id == case.id)
                )
            ).scalars()
        ]
        assert "process.recovered" in actions

    async def test_a_case_left_mid_graph_is_continued_not_restarted(
        self, client: AsyncClient, auth, db_session
    ) -> None:
        """Restarting would feed the initial state in twice, and the appending reducers on the
        worker keys would duplicate every list. Continuing resumes from the checkpoint."""
        headers = await auth("ops_officer")
        created = await client.post(
            "/api/v1/cases",
            headers=headers,
            json={
                "case_type": "kyc_refresh",
                "customer_name": "Old Harbour Trading LLC",
                "priority": "normal",
            },
        )
        case_id = created.json()["id"]
        pdf = simple_pdf(
            "Trade Licence",
            [
                ("Licence number", "CN-9005678"),
                ("Company name (EN)", "Old Harbour Trading LLC"),
                ("Licensing authority", "Department of Economic Development"),
                ("Business activity", "General trading"),
                ("Issue date", "2018-02-01"),
                ("Expiry date", "2020-02-01"),
            ],
            "Synthetic",
        )
        await client.post(
            f"/api/v1/cases/{case_id}/documents",
            headers=headers,
            files={"files": ("tl.pdf", pdf, "application/pdf")},
        )
        await client.post(f"/api/v1/cases/{case_id}/start", headers=headers)
        await pipeline.drain(timeout=60.0)

        detail = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
        assert detail["status"] == "needs_review"
        documents_before = len(detail["documents"])
        fields_before = len(detail["fields"])
        tasks_before = len(detail["review_tasks"])

        # Pretend the crash happened while the graph was running.
        case = (
            await db_session.execute(select(models.Case).where(models.Case.id == case_id))
        ).scalar_one()
        case.status = CaseStatus.processing
        await db_session.commit()

        status = await runner.continue_case(case.id)

        assert status == CaseStatus.needs_review.value, "it is still waiting for a person"
        after = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
        assert len(after["fields"]) == fields_before, "continuing must not duplicate fields"
        assert len(after["documents"]) == documents_before
        assert len(after["review_tasks"]) == tasks_before, "one review, not two"


# ----------------------------------------------------------- choosing an engine


class _FakeConductor:
    """A Conductor that answers exactly what a test needs, with no server involved."""

    def __init__(self, *, healthy: bool = True) -> None:
        self.healthy = healthy
        self.completed: list[dict] = []
        self.started: list[dict] = []
        self.tasks = [
            {"taskId": "task-human", "taskType": "HUMAN", "status": "IN_PROGRESS"},
            {"taskId": "task-wait", "taskType": "WAIT", "status": "IN_PROGRESS"},
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if not self.healthy:
            # A server that is down is down: the health check must not be able to find a
            # second endpoint that happens to answer and call that "reachable".
            return httpx.Response(503, json={"healthy": False})
        if path == "/health":
            return httpx.Response(200, json={"healthy": True})
        if path.startswith("/api/metadata"):
            return httpx.Response(200, json={})
        if path == "/api/workflow" and request.method == "POST":
            body = json.loads(request.content)
            self.started.append(body)
            return httpx.Response(200, text="wf-12345")
        if path.startswith("/api/workflow/"):
            return httpx.Response(
                200,
                json={"workflowId": "wf-12345", "status": "RUNNING", "tasks": self.tasks},
            )
        if path == "/api/tasks" and request.method == "POST":
            body = json.loads(request.content)
            self.completed.append(body)
            for task in self.tasks:
                if task["taskId"] == body["taskId"]:
                    task["status"] = body["status"]
            return httpx.Response(200, text="ok")
        return httpx.Response(404)

    def client(self) -> ConductorClient:
        client = ConductorClient("http://conductor.test:8080")
        client._client = httpx.AsyncClient(
            base_url="http://conductor.test:8080",
            transport=httpx.MockTransport(self.handler),
        )
        return client


class TestChoosingAnEngine:
    async def test_a_decision_goes_back_to_the_engine_that_started_the_case(
        self, db_session
    ) -> None:
        """A case Conductor started must not have its decision handed to the fallback."""
        from app.db.enums import ActorType
        from app.process import by_name, engine_for_case
        from app.services.events import record_event

        case = await _case(db_session, status=CaseStatus.needs_review)
        await record_event(
            db_session,
            case_id=case.id,
            action=base.STARTED,
            label="started on Conductor",
            actor="test",
            actor_type=ActorType.system,
            detail={"engine": "conductor", "workflow_id": "wf-12345"},
        )
        await db_session.commit()

        engine = await engine_for_case(db_session, case)
        assert engine.name == "conductor"
        assert by_name("conductor").name == "conductor"

    async def test_a_case_with_no_recorded_start_uses_todays_engine(self, db_session) -> None:
        from app.process import engine_for_case

        case = await _case(db_session, status=CaseStatus.needs_review)
        await db_session.commit()
        engine = await engine_for_case(db_session, case)
        assert engine.name == "inprocess"

    async def test_an_unreachable_conductor_is_reported_not_hidden(self) -> None:
        fake = _FakeConductor(healthy=False)
        engine = ConductorEngine(fake.client())
        health = await engine.health()
        assert health.reachable is False
        assert "not reachable" in health.detail or "503" in health.detail
        await engine.client.close()

    async def test_the_fallback_is_honest_about_what_it_lacks(self) -> None:
        health = await InProcessEngine().health()
        assert health.reachable is True
        assert "without a task queue" in health.detail


class TestTheConductorEngine:
    async def test_starting_a_case_makes_the_workflow_id_the_thread_id(
        self, db_session
    ) -> None:
        """One identifier for the process, the reasoning and the audit trail."""
        fake = _FakeConductor()
        engine = ConductorEngine(fake.client())
        case = await _case(db_session, status=CaseStatus.intake)
        await db_session.commit()

        workflow_id = await engine.start_case(case.id)

        assert workflow_id == "wf-12345"
        await db_session.refresh(case)
        assert case.thread_id == "wf-12345"
        assert fake.started[0]["idempotencyKey"] == str(case.id)
        await engine.client.close()

    async def test_a_decision_completes_the_human_task_and_releases_the_timer(
        self, db_session
    ) -> None:
        fake = _FakeConductor()
        engine = ConductorEngine(fake.client())
        case = await _case(db_session, status=CaseStatus.needs_review)
        case.thread_id = "wf-12345"
        await db_session.commit()

        await engine.submit_decision(case.id, "approve", {"company_name_en": "Fixed LLC"})

        completed = {entry["taskId"]: entry for entry in fake.completed}
        assert completed["task-human"]["outputData"]["decision"] == "approve"
        # The timer branch is released so the instance can finish, and only after the human
        # task — otherwise the escalation step could see a review that is still open.
        assert list(completed) == ["task-human", "task-wait"]
        await engine.client.close()

    async def test_conductor_owns_crash_recovery(self) -> None:
        """The fallback sweeps for stuck cases; Conductor redelivers, so it has nothing to do."""
        fake = _FakeConductor()
        engine = ConductorEngine(fake.client())
        assert await engine.recover() == 0
        await engine.client.close()


# ---------------------------------------------------------------------- the API


class TestTheProcessApi:
    async def test_health_names_the_engine_actually_in_use(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("ops_officer")
        body = (await client.get("/api/v1/process/health", headers=headers)).json()
        assert body["active"] == "inprocess"
        assert body["process"]["workflow"] == definition.WORKFLOW_NAME
        assert body["process"]["steps"], "the UI needs the step list"

    async def test_the_definition_is_served_from_the_code(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("auditor")
        body = (await client.get("/api/v1/process/definition", headers=headers)).json()
        assert [step["ref"] for step in body["steps"]] == [
            step.ref for step in definition.STEPS
        ]
        assert "flowchart" in body["mermaid"]

    async def test_a_reviewer_cannot_run_the_sla_sweep(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("reviewer")
        response = await client.post("/api/v1/process/sla/sweep", headers=headers)
        assert response.status_code == 403

    async def test_a_supervisor_can_run_the_sla_sweep(
        self, client: AsyncClient, auth
    ) -> None:
        headers = await auth("supervisor")
        response = await client.post("/api/v1/process/sla/sweep", headers=headers)
        assert response.status_code == 200
        assert "note" in response.json()

    async def test_the_case_view_shows_the_steps_and_the_posting(
        self, client: AsyncClient, auth, db_session
    ) -> None:
        case = await _case(db_session, status=CaseStatus.approved, straight_through=True)
        await db_session.commit()
        await posting.post_case(case.id)

        headers = await auth("ops_officer")
        body = (await client.get(f"/api/v1/cases/{case.id}/process", headers=headers)).json()

        assert body["workflow_name"] == definition.WORKFLOW_NAME
        assert body["posting"]["status"] == "posted"
        assert body["posting"]["simulated"] is True
        post_step = next(step for step in body["steps"] if step["ref"] == "post")
        assert post_step["writes_externally"] is True
