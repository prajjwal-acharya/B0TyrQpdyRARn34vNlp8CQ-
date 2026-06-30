"""Stub Phase 5 extraction subgraph for passports.

Phase 2B only needs to prove that conditional dispatch reaches the correct
doc-type branch (visible in LangGraph Studio); real field extraction is
implemented in Phase 5.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from services.router.router.schemas import RouterState

DOC_TYPE = "passport"


def stub_extract(state: RouterState) -> dict:
    """Placeholder node — marks that this subgraph was entered."""
    return {"dispatched_to": DOC_TYPE}


def build_passport_graph():
    """Compile and return the placeholder passport extraction subgraph."""
    builder: StateGraph = StateGraph(RouterState)
    builder.add_node("stub_extract", stub_extract)
    builder.set_entry_point("stub_extract")
    builder.add_edge("stub_extract", END)
    return builder.compile(name=f"{DOC_TYPE}_subgraph")


passport_graph = build_passport_graph()

__all__ = ["build_passport_graph", "passport_graph"]
