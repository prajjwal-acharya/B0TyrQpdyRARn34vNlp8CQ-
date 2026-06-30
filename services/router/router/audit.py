"""Routing-decision audit log (Phase 12 — Observability).

Every classification made by the router node is persisted to the
``routing_decisions`` Postgres table so the full rationale behind any job's
doc-type routing — which model decided, at what confidence, and why — can be
queried by ``job_id`` after the fact.
"""
from __future__ import annotations

import logging
import uuid

from shared.db import SessionLocal
from shared.models import RoutingDecision

from .schemas import RouterDecision

logger = logging.getLogger(__name__)


def log_routing_decision(job_id: str, decision: RouterDecision, model_used: str) -> None:
    """Write a routing decision to the audit log.

    Best-effort: a logging failure must never break the routing pipeline, so
    any exception is caught and logged rather than propagated.
    """
    db = SessionLocal()
    try:
        db.add(
            RoutingDecision(
                job_id=uuid.UUID(job_id),
                doc_type=decision.doc_type.value,
                confidence=decision.confidence,
                model_used=model_used,
                reasoning=decision.reasoning,
                fallback_used=decision.fallback_used,
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to write routing decision audit log (job_id=%s)", job_id)
        db.rollback()
    finally:
        db.close()


def get_routing_decision(job_id: str) -> RoutingDecision | None:
    """Fetch the most recent routing decision logged for a job_id."""
    db = SessionLocal()
    try:
        return (
            db.query(RoutingDecision)
            .filter(RoutingDecision.job_id == uuid.UUID(job_id))
            .order_by(RoutingDecision.created_at.desc())
            .first()
        )
    finally:
        db.close()


__all__ = ["get_routing_decision", "log_routing_decision"]
