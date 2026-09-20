"""Shapes the process layer returns to the browser."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

StepStatus = Literal["pending", "running", "waiting", "completed", "skipped", "failed"]


class ProcessStepOut(BaseModel):
    ref: str
    label: str
    kind: str
    status: StepStatus
    at: str | None = None
    detail: str = ""
    writes_externally: bool = False


class PostingOut(BaseModel):
    """What happened when the case was handed to the (simulated) system of record."""

    status: Literal["posted", "skipped", "failed"]
    reference: str | None = None
    customer_id: str = ""
    approval_kind: str = ""
    approved_by: str = ""
    duplicate: bool = False
    idempotency_key: str = ""
    note: str = ""
    posted_at: str | None = None
    simulated: bool = True


class ProcessStatusOut(BaseModel):
    """Where one case is in the business process."""

    engine: str
    workflow_name: str
    workflow_version: int
    workflow_id: str
    route: str
    steps: list[ProcessStepOut]
    posting_reference: str | None = None
    escalated: bool = False
    started: bool = False
    finished: bool = False
    note: str = ""
    # Conductor's own view, when Conductor ran the case and answered.
    live: dict[str, Any] | None = None
    # The posting attempt, if the case reached that step. `None` means it has not yet.
    posting: PostingOut | None = None


class EngineHealthOut(BaseModel):
    engine: str
    reachable: bool
    detail: str
    workflow_registered: bool = False
    url: str = ""


class ProcessStepDefinitionOut(BaseModel):
    ref: str
    kind: str
    label: str
    description: str
    queue: str = ""
    writes_externally: bool = False
    only_on_route: str = ""


class ProcessDefinitionOut(BaseModel):
    workflow: str
    version: int
    sla_hours: int
    steps: list[ProcessStepDefinitionOut]
    worker_queues: list[str]
    mermaid: str


class ProcessHealthOut(BaseModel):
    configured: Literal["auto", "conductor", "inprocess"]
    active: str
    # True when `auto` wanted Conductor and had to use the fallback. Shown in the UI, because a
    # demo running on the fallback must not look like one running on Conductor.
    fell_back: bool
    engines: list[EngineHealthOut]
    process: ProcessDefinitionOut


class SlaSweepOut(BaseModel):
    escalated: int
    note: str


class AuditIntegrityOut(BaseModel):
    append_only_enforced: bool
    trigger: str
    detail: str
    rows: int
    first_seq: int | None = None
    last_seq: int | None = None
    oldest: str | None = None
    newest: str | None = None
    limits: str
