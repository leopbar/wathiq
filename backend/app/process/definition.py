"""The business process, declared once.

This is the **process layer**: the order in which business steps happen, who has to act, and
what must be true before money-side work is done. It is deliberately separate from the agent
graph (`app/agent/graph.py`), which is the **reasoning layer**. The two answer different
questions:

* the graph asks "what does this document say, and how sure am I?";
* the process asks "has a human approved, has the SLA expired, has this been posted already?".

Everything in this module is data. Both engines read it:

* `ConductorEngine` turns it into Conductor JSON and registers it with the Conductor server,
  which then owns the state machine;
* `InProcessEngine` walks the same steps itself, for a machine that cannot spare the ~2 GB
  Conductor needs.

Because the step list, the Conductor JSON and the diagram all come from this one file, the
About screen cannot draw a process we do not run. A test asserts that the JSON and the step
list refer to exactly the same steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings

WORKFLOW_NAME = "wathiq_kyc_refresh"
WORKFLOW_VERSION = 1

# Conductor requires an owner on every definition. Synthetic, like all data in this project.
OWNER_EMAIL = "wathiq-demo@example.invalid"

StepKind = Literal["simple", "human", "wait", "switch", "fork", "join"]

# The two routes out of the agent step. Strings rather than a boolean: Conductor's switch
# compares the value as text, and "review"/"straight_through" cannot be misread the way
# "true"/"True"/"1" can.
ROUTE_REVIEW = "review"
ROUTE_STRAIGHT_THROUGH = "straight_through"


@dataclass(frozen=True)
class Step:
    """One step of the business process.

    `ref` is the task reference name — the identifier Conductor uses inside a workflow
    instance, and the key both engines report progress under. `queue` is the task type a
    worker polls for; control-flow steps (switch, fork, join, wait) have none, because
    Conductor evaluates them itself and the in-process engine evaluates them in Python.
    """

    ref: str
    kind: StepKind
    label: str
    description: str
    queue: str = ""
    # True for a step that changes something outside Wathiq. Exactly one step does.
    writes_externally: bool = False
    # Steps that only happen on one of the two routes.
    only_on_route: str = ""


STEPS: list[Step] = [
    Step(
        ref="intake",
        kind="simple",
        queue="wathiq_intake",
        label="Intake",
        description=(
            "Check the case is startable (it has documents and is not already finished) and "
            "record which engine is running it."
        ),
    ),
    Step(
        ref="agent",
        kind="simple",
        queue="wathiq_agent",
        label="Agent (LangGraph)",
        description=(
            "Run the whole reasoning graph: guardrails, parallel extraction, critic, "
            "investigator, validation. Ends either at the review gate or finished."
        ),
    ),
    Step(
        ref="review_needed",
        kind="switch",
        label="Does a human have to look?",
        description=(
            "The agent's own answer decides the route. Nothing else in the process may "
            "override it."
        ),
    ),
    Step(
        ref="human_review",
        kind="human",
        queue="wathiq_human_review",
        label="Human review",
        description=(
            "The process stops here until a named reviewer decides. This is a task in the "
            "process, not a flag on a row, which is why the wait survives a restart."
        ),
        only_on_route=ROUTE_REVIEW,
    ),
    Step(
        ref="sla_timer",
        kind="wait",
        label=f"SLA timer ({settings.review_sla_hours}h)",
        description=(
            "Runs beside the review, not after it. If it fires first, the review is late."
        ),
        only_on_route=ROUTE_REVIEW,
    ),
    Step(
        ref="sla_escalation",
        kind="simple",
        queue="wathiq_escalate",
        label="Escalate to a supervisor",
        description=(
            "Reassigns the overdue review to the supervisor queue and records it. The review "
            "is not cancelled — it still needs an answer, now from someone else."
        ),
        only_on_route=ROUTE_REVIEW,
    ),
    Step(
        ref="review_join",
        kind="join",
        label="Wait for the decision",
        description=(
            "Joins on the review alone. A fired timer escalates but never finishes the case "
            "on a human's behalf."
        ),
        only_on_route=ROUTE_REVIEW,
    ),
    Step(
        ref="apply_decision",
        kind="simple",
        queue="wathiq_apply_decision",
        label="Apply the decision",
        description=(
            "Resumes the agent graph from its checkpoint with the reviewer's answer and "
            "corrections."
        ),
        only_on_route=ROUTE_REVIEW,
    ),
    Step(
        ref="post",
        kind="simple",
        queue="wathiq_post",
        label="Post to core banking",
        description=(
            "The only step that writes outside Wathiq. Refuses unless the case was approved, "
            "and carries an idempotency key so a retry cannot post twice."
        ),
        writes_externally=True,
    ),
    Step(
        ref="audit",
        kind="simple",
        queue="wathiq_audit",
        label="Seal the audit trail",
        description=(
            "Writes the closing entry: who decided, what was posted, which prompt and rule "
            "pack versions judged the case."
        ),
    ),
]

STEP_BY_REF: dict[str, Step] = {step.ref: step for step in STEPS}

# The task queues a worker must poll. Control-flow steps have none.
WORKER_QUEUES: list[str] = [step.queue for step in STEPS if step.kind == "simple" and step.queue]

HUMAN_QUEUE = "wathiq_human_review"

# 30 days. Conductor insists on at least one second here even for a task no worker polls.
HUMAN_RESPONSE_TIMEOUT_SECONDS = 30 * 24 * 60 * 60


def steps_for_route(route: str) -> list[Step]:
    """The steps that actually run on one of the two routes."""
    return [step for step in STEPS if not step.only_on_route or step.only_on_route == route]


# --------------------------------------------------------------------- Conductor JSON


def _task(ref: str, task_type: str, **extra: Any) -> dict[str, Any]:
    step = STEP_BY_REF[ref]
    task: dict[str, Any] = {
        "name": step.queue or ref,
        "taskReferenceName": ref,
        "type": task_type,
        "description": step.description,
    }
    task.update(extra)
    return task


def _case_input() -> dict[str, Any]:
    """Every worker task gets the case id and nothing else.

    The worker reads the case from the database itself. Keeping the payload this small means
    no copy of a customer's data is held in Conductor, which is a different system with its
    own retention — and it is why the workflow input is safe to show in the Conductor UI.
    """
    return {"case_id": "${workflow.input.case_id}"}


def workflow_definition() -> dict[str, Any]:
    """The Conductor workflow definition, ready to register."""
    review_branch: list[dict[str, Any]] = [
        {
            "name": "review_and_timer",
            "taskReferenceName": "review_and_timer",
            "type": "FORK_JOIN",
            "description": "The review and its SLA timer run side by side.",
            "forkTasks": [
                [
                    _task(
                        "human_review",
                        "HUMAN",
                        inputParameters={
                            **_case_input(),
                            "reasons": "${agent.output.review_reasons}",
                        },
                    )
                ],
                [
                    _task(
                        "sla_timer",
                        "WAIT",
                        inputParameters={"duration": f"{settings.review_sla_hours}h"},
                    ),
                    _task("sla_escalation", "SIMPLE", inputParameters=_case_input()),
                ],
            ],
        },
        # joinOn lists only the review: the timer branch may still be waiting, and the case
        # must not continue until a person has answered.
        {
            "name": "review_join",
            "taskReferenceName": "review_join",
            "type": "JOIN",
            "joinOn": ["human_review"],
        },
        _task(
            "apply_decision",
            "SIMPLE",
            inputParameters={
                **_case_input(),
                "decision": "${human_review.output.decision}",
                "corrections": "${human_review.output.corrections}",
            },
        ),
    ]

    return {
        "name": WORKFLOW_NAME,
        "version": WORKFLOW_VERSION,
        "description": "Corporate KYC refresh: intake, agent, human review, posting, audit.",
        "ownerEmail": OWNER_EMAIL,
        "schemaVersion": 2,
        "restartable": True,
        "workflowStatusListenerEnabled": False,
        # ALERT_ONLY: a case that waits a long time for a person is normal, and must never be
        # failed by the orchestrator. Lateness is handled by the SLA branch, which escalates.
        "timeoutPolicy": "ALERT_ONLY",
        "timeoutSeconds": 0,
        "inputParameters": ["case_id", "case_reference"],
        "outputParameters": {
            "case_id": "${workflow.input.case_id}",
            "status": "${audit.output.status}",
            "posting_reference": "${post.output.reference}",
        },
        "tasks": [
            # Intake is also where the two identifiers are tied together: it receives
            # Conductor's own workflow id and makes sure the case's LangGraph thread id is the
            # same string, before any step needs it.
            _task(
                "intake",
                "SIMPLE",
                inputParameters={**_case_input(), "workflow_id": "${workflow.workflowId}"},
            ),
            _task("agent", "SIMPLE", inputParameters=_case_input()),
            _task(
                "review_needed",
                "SWITCH",
                evaluatorType="value-param",
                expression="route",
                inputParameters={"route": "${agent.output.route}"},
                decisionCases={ROUTE_REVIEW: review_branch},
                defaultCase=[],
            ),
            _task("post", "SIMPLE", inputParameters=_case_input()),
            _task("audit", "SIMPLE", inputParameters=_case_input()),
        ],
    }


def task_definitions() -> list[dict[str, Any]]:
    """Retry and timeout policy per task type.

    The numbers say what kind of failure each step can have. The agent step is slow and worth
    retrying. The posting step is retried too — which is only safe because of the idempotency
    key, and is the clearest example of why that key exists.
    """
    common = {
        "ownerEmail": OWNER_EMAIL,
        "retryLogic": "EXPONENTIAL_BACKOFF",
        "retryDelaySeconds": 10,
        "timeoutPolicy": "RETRY",
    }
    defs: list[dict[str, Any]] = [
        {
            **common,
            "name": "wathiq_intake",
            "description": "Validate the case and record the engine.",
            "retryCount": 2,
            "timeoutSeconds": 60,
            "responseTimeoutSeconds": 30,
        },
        {
            **common,
            "name": "wathiq_agent",
            "description": "Run the LangGraph reasoning graph for the case.",
            "retryCount": 1,
            "timeoutSeconds": 900,
            # The lease on a polled task. If the worker dies, Conductor gives the task to
            # someone else after this — which is the crash recovery, and is safe because the
            # step continues the graph from its checkpoint rather than starting it again.
            "responseTimeoutSeconds": 300,
            # The graph is the expensive step; a handful at a time keeps a 16 GB laptop alive.
            "concurrentExecLimit": 4,
        },
        {
            **common,
            "name": "wathiq_apply_decision",
            "description": "Resume the graph with the reviewer's decision.",
            "retryCount": 2,
            "timeoutSeconds": 600,
            "responseTimeoutSeconds": 300,
        },
        {
            **common,
            "name": "wathiq_post",
            "description": "Idempotent posting to the simulated core banking system.",
            "retryCount": 3,
            "timeoutSeconds": 120,
            "responseTimeoutSeconds": 60,
        },
        {
            **common,
            "name": "wathiq_audit",
            "description": "Write the closing audit entry.",
            "retryCount": 3,
            "timeoutSeconds": 60,
            "responseTimeoutSeconds": 30,
        },
        {
            **common,
            "name": "wathiq_escalate",
            "description": "Escalate an overdue review to a supervisor.",
            "retryCount": 2,
            "timeoutSeconds": 60,
            "responseTimeoutSeconds": 30,
        },
        {
            "ownerEmail": OWNER_EMAIL,
            "name": HUMAN_QUEUE,
            "description": "A reviewer's decision. Waits as long as it has to.",
            "retryCount": 0,
            # `timeoutSeconds: 0` means "never time out": a person may be away for the weekend,
            # and the SLA branch is what notices lateness — by escalating, not by failing the
            # case. `responseTimeoutSeconds` has to be at least 1 (Conductor rejects 0), so it
            # is set to 30 days, and `ALERT_ONLY` means that even reaching it only logs.
            "timeoutSeconds": 0,
            "responseTimeoutSeconds": HUMAN_RESPONSE_TIMEOUT_SECONDS,
            "timeoutPolicy": "ALERT_ONLY",
        },
    ]
    return defs


# --------------------------------------------------------------------------- diagram


def mermaid() -> str:
    """The process as a diagram, for the About screen.

    Hand-drawn rather than generated so the two things that matter are visible: the timer runs
    *beside* the review, and only one step writes outside Wathiq.
    """
    sla = settings.review_sla_hours
    return f"""flowchart TD
    start([Case started]) --> intake[Intake<br/>wathiq_intake]
    intake --> agent[Agent task<br/>runs the whole LangGraph graph]
    agent --> route{{Does a human<br/>have to look?}}

    route -->|straight_through| post
    route -->|review| fork

    fork[Fork] --> human[HUMAN task<br/>waits for a reviewer]
    fork --> timer[WAIT {sla}h<br/>SLA timer]
    timer --> escalate[Escalate to supervisor<br/>wathiq_escalate]
    human --> join[Join on the review only]
    escalate -.->|review still open| human
    join --> apply[Apply decision<br/>resume the graph]
    apply --> post

    post[Post to core banking<br/>idempotency key, approved only]
    post --> audit[Seal the audit trail]
    audit --> done([Case closed])

    classDef writes fill:#7f1d1d,stroke:#ef4444,color:#fff
    classDef waits fill:#1e3a5f,stroke:#3b82f6,color:#fff
    class post writes
    class human,timer waits
"""


def describe() -> dict[str, Any]:
    """The process layer as the API reports it, for the About and Settings screens."""
    return {
        "workflow": WORKFLOW_NAME,
        "version": WORKFLOW_VERSION,
        "sla_hours": settings.review_sla_hours,
        "steps": [
            {
                "ref": step.ref,
                "kind": step.kind,
                "label": step.label,
                "description": step.description,
                "queue": step.queue,
                "writes_externally": step.writes_externally,
                "only_on_route": step.only_on_route,
            }
            for step in STEPS
        ],
        "worker_queues": WORKER_QUEUES,
        "mermaid": mermaid(),
    }


__all__ = [
    "HUMAN_QUEUE",
    "OWNER_EMAIL",
    "ROUTE_REVIEW",
    "ROUTE_STRAIGHT_THROUGH",
    "STEPS",
    "STEP_BY_REF",
    "WORKER_QUEUES",
    "WORKFLOW_NAME",
    "WORKFLOW_VERSION",
    "Step",
    "describe",
    "mermaid",
    "steps_for_route",
    "task_definitions",
    "workflow_definition",
]
