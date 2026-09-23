"""Wiring the nodes into a graph.

    ocr -> guardrails -> supervisor =Send=> extract_worker (parallel)
        -> critic -> investigator -> validate -> (review_gate) -> finalize

Two branches, and they are the two decisions the system makes:

* after `supervisor`, `fan_out` returns one `Send` per document, which is what runs the
  extraction workers in parallel instead of one after another;
* after `validate`, `needs_human` decides whether a person has to look. If nobody does, the
  case goes straight to finalize — that is the "straight-through" path the dashboard counts.

Everything is built here in one place so the picture on the About screen can be generated from
the same graph the pipeline compiles, and cannot drift from it.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    critic_node,
    extract_worker_node,
    fan_out,
    finalize_node,
    guardrails_node,
    investigator_node,
    needs_human,
    ocr_node,
    review_gate_node,
    supervisor_node,
    validate_node,
)
from app.agent.state import CaseState
from app.azure import monitor

# The steps, in order, with the label the UI shows. One source of truth for the graph, the
# stepper and the "what happens next" panel, so none of them can describe a pipeline we do
# not run.
STEP_LABELS: list[tuple[str, str]] = [
    ("ocr", "Read text"),
    ("guardrails", "Guardrails"),
    ("supervisor", "Classify and plan"),
    ("extract", "Extract (parallel)"),
    ("critic", "Critic"),
    ("investigate", "Investigate"),
    ("validate", "Validate"),
    ("review_gate", "Review gate"),
    ("finalize", "Finalize"),
]


def _traced(name: str, node: Any) -> Any:
    """Wrap a node so every entry and exit is one span (M6).

    Done here, once, rather than with a decorator on each of the nine node functions: a node
    added later is traced because it was added to the graph, which is the property worth
    having. With tracing off, `monitor.span` is a no-op context manager.

    The case id is an attribute; nothing from the document is. A trace leaves the building.
    """

    @wraps(node)
    async def traced_node(state: Any, *args: Any, **kwargs: Any) -> Any:
        case_id = state.get("case_id") if isinstance(state, dict) else None
        with monitor.span(f"graph.{name}", node=name, case_id=case_id):
            return await node(state, *args, **kwargs)

    return traced_node


def build_graph() -> StateGraph:
    """Build the graph without compiling it, so tests can compile with their own checkpointer."""
    graph: StateGraph = StateGraph(CaseState)

    for name, node in (
        ("ocr", ocr_node),
        ("guardrails", guardrails_node),
        ("supervisor", supervisor_node),
        ("extract_worker", extract_worker_node),
        ("critic", critic_node),
        ("investigator", investigator_node),
        ("validate", validate_node),
        ("review_gate", review_gate_node),
        ("finalize", finalize_node),
    ):
        graph.add_node(name, _traced(name, node))

    graph.add_edge(START, "ocr")
    graph.add_edge("ocr", "guardrails")
    graph.add_edge("guardrails", "supervisor")

    # Supervisor-worker: `fan_out` returns a list of Send objects, one per document. They all
    # run in the same superstep, and `critic` runs once, after every one of them has finished.
    graph.add_conditional_edges("supervisor", fan_out, ["extract_worker", "critic"])
    graph.add_edge("extract_worker", "critic")

    graph.add_edge("critic", "investigator")
    graph.add_edge("investigator", "validate")

    # The one routing decision: human or not.
    graph.add_conditional_edges(
        "validate", needs_human, {"review_gate": "review_gate", "finalize": "finalize"}
    )
    graph.add_edge("review_gate", "finalize")
    graph.add_edge("finalize", END)

    return graph


def compile_in_memory():
    """A compiled graph with a throwaway checkpointer — for tests and for the diagram."""
    return build_graph().compile(checkpointer=InMemorySaver())


def mermaid() -> str:
    """The real graph as Mermaid, so the About screen shows what actually runs.

    Drawn by hand rather than from `get_graph().draw_mermaid()` because the generated version
    does not label the branches or say that the workers are parallel, and that is the part
    worth showing.
    """
    return """stateDiagram-v2
    [*] --> ocr
    ocr --> guardrails: text read
    guardrails --> supervisor: prompt shield, content safety, PII tokenised
    supervisor --> extract_worker: Send() — one worker per document, in parallel
    extract_worker --> extract_worker: self-correct on validation errors (max 2)
    extract_worker --> critic: all workers finished
    supervisor --> critic: nothing to extract
    critic --> investigator: verdict on every field
    investigator --> investigator: ReAct loop with MCP tools (max 6 steps)
    investigator --> validate
    validate --> review_gate: something needs a human
    validate --> finalize: confident enough
    review_gate --> review_gate: interrupt() — waits for a reviewer
    review_gate --> finalize: decision applied
    finalize --> [*]
"""
