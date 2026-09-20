"""Turning event-log rows into pipeline-stepper frames.

The event log is the record of what happened, written in the language of the audit trail
("agent.extract.done"). The stepper in the UI thinks in whole steps ("extract", 60% done). This
module is the one place that translates between the two, so the backend and the UI can never
drift apart about what the steps are.

The step list comes from `app.agent.graph`, which is the graph the pipeline actually compiles.
A step cannot appear here that does not run.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.graph import STEP_LABELS

# Where each step's bar sits when it finishes. Intake is not a graph node — it is the upload
# and the queueing that happen before the graph starts — so it is prepended here.
_COMPLETION: dict[str, int] = {
    "intake": 8,
    "ocr": 18,
    "guardrails": 28,
    "supervisor": 40,
    "extract": 58,
    "critic": 70,
    "investigate": 80,
    "validate": 90,
    "review_gate": 96,
    "finalize": 100,
}

# (key, label, percent when this step completes)
STEPS: list[tuple[str, str, int]] = [("intake", "Intake", _COMPLETION["intake"])] + [
    (key, label, _COMPLETION[key]) for key, label in STEP_LABELS
]

_PERCENT = {key: percent for key, _label, percent in STEPS}

# Which step each event action belongs to, and whether it finishes that step.
_ACTION_MAP: dict[str, tuple[str, str]] = {
    "case.created": ("intake", "running"),
    "documents.uploaded": ("intake", "running"),
    "case.started": ("intake", "running"),
    "pipeline.queued": ("intake", "done"),
    "agent.ocr": ("ocr", "done"),
    "agent.guardrails.document": ("guardrails", "running"),
    "agent.guardrails": ("guardrails", "done"),
    "agent.classify": ("supervisor", "running"),
    "agent.supervisor": ("supervisor", "done"),
    "agent.extract": ("extract", "running"),
    "agent.extract.done": ("extract", "done"),
    "agent.critic": ("critic", "done"),
    "agent.investigate.step": ("investigate", "running"),
    "agent.investigate": ("investigate", "done"),
    "agent.finding": ("validate", "running"),
    "agent.validate": ("validate", "done"),
    "pipeline.paused": ("review_gate", "waiting"),
    "review.claimed": ("review_gate", "waiting"),
    "review.approve": ("review_gate", "running"),
    "review.correct": ("review_gate", "running"),
    "review.reject": ("review_gate", "running"),
    "review.escalate": ("review_gate", "waiting"),
    "agent.review.resumed": ("review_gate", "done"),
    "agent.finalize": ("finalize", "running"),
    "pipeline.completed": ("finalize", "done"),
    "pipeline.failed": ("finalize", "failed"),
}


@dataclass(slots=True)
class ProgressFrame:
    node: str
    status: str
    percent: int


def frame_for(action: str) -> ProgressFrame | None:
    """Map one event action to a stepper frame, or None if it is not a pipeline step.

    Returning None matters: plenty of events (a note, a login) belong in the timeline but say
    nothing about pipeline progress, and inventing a step for them would move the bar wrongly.
    """
    mapped = _ACTION_MAP.get(action)
    if mapped is None:
        return None
    node, status = mapped
    percent = _PERCENT[node]
    if status in ("running", "waiting"):
        # Part-way through a step: stop short of the number that means "finished".
        index = [key for key, _l, _p in STEPS].index(node)
        previous = STEPS[index - 1][2] if index else 0
        percent = previous + (percent - previous) // 2
    return ProgressFrame(node=node, status=status, percent=percent)
