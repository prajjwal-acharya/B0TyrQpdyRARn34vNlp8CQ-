"""Explicit fallback branch for unknown / low-confidence doc-type routing.

Reached via the conditional edge in ``graph.py`` when classification produced
no decision at all, or a final confidence (post Groq → Gemini escalation)
below ``LOW_CONFIDENCE_THRESHOLD``. The document is flagged for manual / HITL
review (Phase 8) instead of being silently dispatched into a doc-type
subgraph it may not actually belong to.
"""
from __future__ import annotations

import logging

from .schemas import RouterState

logger = logging.getLogger(__name__)

FALLBACK_NODE = "fallback_review"


def fallback_review(state: RouterState) -> dict:
    """LangGraph node: mark the document as needing manual review."""
    decision = state.get("decision")
    if decision is None:
        logger.warning("Routing fallback: classification produced no decision")
    else:
        logger.warning(
            "Routing fallback: doc_type=%s confidence=%.2f — flagging for manual review",
            decision.doc_type,
            decision.confidence,
        )
    return {"needs_manual_review": True, "dispatched_to": None}


__all__ = ["FALLBACK_NODE", "fallback_review"]
