"""LangGraph graph definition for the Phase 2 routing + dispatch stage.

After classification, a conditional edge dispatches the document to the
doc-type-specific Phase 5 extraction subgraph (stubbed for now — see
``services/extraction/graphs``). An unknown or low-confidence classification
takes an explicit fallback branch instead of silently defaulting to a doc
type.
"""
from __future__ import annotations

import logging
import os

from langgraph.graph import END, StateGraph

from services.extraction.graphs.bank_statement.graph import bank_statement_graph
from services.extraction.graphs.form_16.graph import form_16_graph
from services.extraction.graphs.gst.graph import gst_graph
from services.extraction.graphs.itr.graph import itr_graph
from services.extraction.graphs.passport.graph import passport_graph
from services.extraction.graphs.property_deed.graph import property_deed_graph
from services.extraction.graphs.salary_slip.graph import salary_slip_graph

from .fallback import FALLBACK_NODE, fallback_review
from .node import classify_document
from .schemas import DocType, RouterState

logger = logging.getLogger(__name__)

# Confidence floor applied to the *final* decision (after any Groq → Gemini
# escalation in classify_document). Below this, the classification isn't
# trustworthy enough to dispatch into a doc-type subgraph at all.
LOW_CONFIDENCE_THRESHOLD: float = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.5"))

# doc_type -> (node name, compiled stub extraction subgraph)
_DOC_TYPE_SUBGRAPHS: dict[DocType, tuple[str, object]] = {
    DocType.PASSPORT: ("passport", passport_graph),
    DocType.ITR: ("itr", itr_graph),
    DocType.BANK_STATEMENT: ("bank_statement", bank_statement_graph),
    DocType.FORM_16: ("form_16", form_16_graph),
    DocType.SALARY_SLIP: ("salary_slip", salary_slip_graph),
    DocType.GST: ("gst", gst_graph),
    DocType.PROPERTY_DEED: ("property_deed", property_deed_graph),
}


def route_by_doc_type(state: RouterState) -> str:
    """Conditional-edge function: pick the next node from the classification.

    Returns the matching doc-type subgraph's node name when the classifier
    produced a confident decision. Otherwise returns the explicit fallback
    node — classification failures and low-confidence results are never
    silently routed into a doc-type subgraph.
    """
    decision = state.get("decision")
    if decision is None:
        logger.warning("No classification decision present — routing to fallback")
        return FALLBACK_NODE
    if decision.confidence < LOW_CONFIDENCE_THRESHOLD:
        logger.warning(
            "Low-confidence classification (%s, confidence=%.2f < %.2f) — routing to fallback",
            decision.doc_type,
            decision.confidence,
            LOW_CONFIDENCE_THRESHOLD,
        )
        return FALLBACK_NODE
    return _DOC_TYPE_SUBGRAPHS[decision.doc_type][0]


def build_router_graph():
    """Compile and return the Phase 2 routing + conditional-dispatch StateGraph."""
    builder: StateGraph = StateGraph(RouterState)
    builder.add_node("classify", classify_document)
    builder.add_node(FALLBACK_NODE, fallback_review)
    for node_name, subgraph in _DOC_TYPE_SUBGRAPHS.values():
        builder.add_node(node_name, subgraph)

    builder.set_entry_point("classify")

    path_map = {node_name: node_name for node_name, _ in _DOC_TYPE_SUBGRAPHS.values()}
    path_map[FALLBACK_NODE] = FALLBACK_NODE
    builder.add_conditional_edges("classify", route_by_doc_type, path_map)

    for node_name, _ in _DOC_TYPE_SUBGRAPHS.values():
        builder.add_edge(node_name, END)
    builder.add_edge(FALLBACK_NODE, END)

    return builder.compile()


router_graph = build_router_graph()

__all__ = [
    "LOW_CONFIDENCE_THRESHOLD",
    "build_router_graph",
    "route_by_doc_type",
    "router_graph",
]
