"""Wiring the nodes into a graph.

    ocr -> classify -> extract -> validate -> (review_gate) -> finalize

The only branch is after `validate`: if anything needs a human, the case goes through the
review gate, which pauses the graph. If nothing does, it goes straight to finalize — that is
the "straight-through" path the dashboard counts.

M3 replaces `extract` with a supervisor and parallel workers, and adds a critic and a ReAct
investigator. The shape stays the same, which is why the graph is built here in one place.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    classify_node,
    extract_node,
    finalize_node,
    needs_human,
    ocr_node,
    review_gate_node,
    validate_node,
)
from app.agent.state import CaseState


def build_graph() -> StateGraph:
    """Build the graph without compiling it, so tests can compile with their own checkpointer."""
    graph: StateGraph = StateGraph(CaseState)

    graph.add_node("ocr", ocr_node)
    graph.add_node("classify", classify_node)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("review_gate", review_gate_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "ocr")
    graph.add_edge("ocr", "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "validate")
    # The one decision in the graph: human or not.
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
    does not label the branch, and the label is the interesting part.
    """
    return """stateDiagram-v2
    [*] --> ocr
    ocr --> classify
    classify --> extract
    extract --> validate
    validate --> review_gate: something needs a human
    validate --> finalize: confident enough
    review_gate --> review_gate: interrupt() — waits for a reviewer
    review_gate --> finalize: decision applied
    finalize --> [*]
"""
