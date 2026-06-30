"""LangGraph graph definition for the Phase 2 routing stage."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from .node import classify_document
from .schemas import RouterState


def build_router_graph():
    """Compile and return the routing StateGraph."""
    builder: StateGraph = StateGraph(RouterState)
    builder.add_node("classify", classify_document)
    builder.set_entry_point("classify")
    builder.add_edge("classify", END)
    return builder.compile()


router_graph = build_router_graph()

__all__ = ["build_router_graph", "router_graph"]
