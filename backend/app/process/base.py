"""What a process engine is, and how a case's position in the process is described.

Two engines implement `ProcessEngine`:

* `ConductorEngine` — Orkes Conductor owns the state machine. Durable, and visible in
  Conductor's own UI.
* `InProcessEngine` — the same steps walked by Python in the API container. It exists because
  Conductor needs about 2 GB of RAM, and a demo must not depend on that.

Both are honest about which one ran a case: the engine name is written into the case's event
log at the start, so a case processed by the fallback can never be mistaken for one that went
through Conductor.

A case's position in the process is **not** read from the engine. It is derived from the
append-only event log by `status_from_events`, for three reasons: it works identically for
both engines, it survives a restart, and it cannot disagree with the audit trail — because it
*is* the audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from app.process import definition

StepStatus = Literal["pending", "running", "waiting", "completed", "skipped", "failed"]

# Event actions the process layer writes. Kept here so the writers and the reader agree.
STARTED = "process.started"
STEP = "process.step"
WAITING = "process.waiting"
ESCALATED = "process.escalated"
POSTED = "process.posted"
POST_SKIPPED = "process.post.skipped"
COMPLETED = "process.completed"
FAILED = "process.failed"


@dataclass(frozen=True)
class EngineHealth:
    """Whether the chosen engine is actually usable, in plain words."""

    engine: str
    reachable: bool
    detail: str
    workflow_registered: bool = False
    url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "reachable": self.reachable,
            "detail": self.detail,
            "workflow_registered": self.workflow_registered,
            "url": self.url,
        }


@dataclass
class StepState:
    """One step of the process, as it stands for one case."""

    ref: str
    label: str
    kind: str
    status: StepStatus = "pending"
    at: datetime | None = None
    detail: str = ""
    writes_externally: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "label": self.label,
            "kind": self.kind,
            "status": self.status,
            "at": self.at.isoformat() if self.at else None,
            "detail": self.detail,
            "writes_externally": self.writes_externally,
        }


@dataclass
class ProcessStatus:
    """Where one case is in the business process."""

    engine: str = ""
    workflow_name: str = definition.WORKFLOW_NAME
    workflow_version: int = definition.WORKFLOW_VERSION
    workflow_id: str = ""
    route: str = ""
    steps: list[StepState] = field(default_factory=list)
    posting_reference: str | None = None
    escalated: bool = False
    started: bool = False
    finished: bool = False
    note: str = ""
    # Filled in only by the Conductor engine, and only when the server answered.
    live: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "workflow_name": self.workflow_name,
            "workflow_version": self.workflow_version,
            "workflow_id": self.workflow_id,
            "route": self.route,
            "steps": [step.as_dict() for step in self.steps],
            "posting_reference": self.posting_reference,
            "escalated": self.escalated,
            "started": self.started,
            "finished": self.finished,
            "note": self.note,
            "live": self.live,
        }


@runtime_checkable
class ProcessEngine(Protocol):
    """The process layer, from the API's point of view.

    Deliberately small. The API knows two verbs — "start this case" and "a reviewer decided" —
    and nothing about Conductor, queues or task ids.
    """

    name: str

    async def start_case(self, case_id: UUID) -> str:
        """Begin the process for a case. Returns the workflow instance id."""
        ...

    async def submit_decision(
        self, case_id: UUID, decision: str, corrections: dict[str, str] | None = None
    ) -> None:
        """Hand a reviewer's answer to the waiting human step."""
        ...

    async def health(self) -> EngineHealth:
        """Whether this engine can run a case right now."""
        ...

    async def status(self, case: Any) -> ProcessStatus:
        """Where this case is in the process."""
        ...


def status_from_events(
    *,
    engine: str,
    workflow_id: str,
    events: list[Any],
    case_status: str,
) -> ProcessStatus:
    """Rebuild a case's process position from its event log.

    The log is append-only, so this is a pure read of facts that were recorded when they
    happened. A step the log does not mention has not run — which is why a case that stopped
    halfway shows the truth rather than an optimistic guess.
    """
    status = ProcessStatus(engine=engine, workflow_id=workflow_id)

    outcomes: dict[str, tuple[str, datetime | None, str]] = {}
    for event in events:
        action = getattr(event, "action", "")
        detail = getattr(event, "detail", None) or {}
        created = getattr(event, "created_at", None)

        if action == STARTED:
            status.started = True
            status.engine = str(detail.get("engine") or engine)
            status.workflow_id = str(detail.get("workflow_id") or workflow_id)
        elif action == STEP:
            ref = str(detail.get("ref", ""))
            if ref:
                outcomes[ref] = (
                    str(detail.get("outcome", "completed")),
                    created,
                    str(detail.get("note", "")),
                )
            if detail.get("route"):
                status.route = str(detail["route"])
        elif action == WAITING:
            outcomes["human_review"] = ("waiting", created, str(detail.get("note", "")))
        elif action == ESCALATED:
            status.escalated = True
        elif action in (POSTED, POST_SKIPPED):
            # `services.posting` writes the authoritative record of the posting step, so it is
            # read as that step rather than duplicated by a second event.
            status.posting_reference = detail.get("reference")
            outcomes["post"] = (
                "completed" if action == POSTED else "skipped",
                created,
                str(detail.get("note", "")),
            )
        elif action == COMPLETED:
            status.finished = True
        elif action == FAILED:
            ref = str(detail.get("ref", ""))
            if ref:
                outcomes[ref] = ("failed", created, str(detail.get("error", "")))

    route = status.route or (
        definition.ROUTE_REVIEW
        if case_status in {"needs_review", "in_review"} or "human_review" in outcomes
        else ""
    )
    steps = definition.steps_for_route(route) if route else list(definition.STEPS)

    # Everything up to the last step the log mentions has had its turn. A step in that stretch
    # with nothing recorded did not run — the case went the other way round it, or the step had
    # nothing to do — so it reads "skipped" rather than sitting at "pending" underneath steps
    # that have already finished.
    last_recorded = -1
    for index, step in enumerate(steps):
        if step.ref in outcomes:
            last_recorded = index

    running_assigned = False
    for index, step in enumerate(steps):
        state = StepState(
            ref=step.ref,
            label=step.label,
            kind=step.kind,
            writes_externally=step.writes_externally,
        )
        recorded = outcomes.get(step.ref)
        if recorded is not None:
            outcome, at, note = recorded
            state.status = outcome  # type: ignore[assignment]
            state.at = at
            state.detail = note
        elif index < last_recorded:
            state.status = "skipped"
        elif (
            status.started
            and not status.finished
            and not running_assigned
            and case_status not in {"rejected", "failed"}
        ):
            # The first step with nothing recorded is the one being worked on. Anything after
            # it is genuinely unknown, and says "pending" rather than pretending.
            state.status = "running"
            running_assigned = True
        status.steps.append(state)

    if route:
        status.route = route
    return status
