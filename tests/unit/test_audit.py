"""Unit tests for the Phase 2 routing-decision audit log (Phase 12 — Observability).

Postgres I/O is mocked via `SessionLocal` — these tests only assert the
shape of the write/read calls, not real database behavior.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from services.router.router.audit import get_routing_decision, log_routing_decision
from services.router.router.schemas import DocType, RouterDecision


def _decision() -> RouterDecision:
    return RouterDecision(
        doc_type=DocType.PASSPORT,
        confidence=0.92,
        reasoning="has photo page and MRZ",
        fallback_used=False,
    )


# ---------------------------------------------------------------------------
# log_routing_decision
# ---------------------------------------------------------------------------

@patch("services.router.router.audit.SessionLocal")
def test_log_routing_decision_writes_and_commits(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    job_id = str(uuid.uuid4())

    log_routing_decision(job_id, _decision(), model_used="groq:llama3-8b-8192")

    mock_db.add.assert_called_once()
    row = mock_db.add.call_args.args[0]
    assert str(row.job_id) == job_id
    assert row.doc_type == DocType.PASSPORT.value
    assert row.confidence == 0.92
    assert row.model_used == "groq:llama3-8b-8192"
    assert row.reasoning == "has photo page and MRZ"
    assert row.fallback_used is False
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


@patch("services.router.router.audit.SessionLocal")
def test_log_routing_decision_swallows_db_errors(mock_session_local):
    """A logging failure must never raise — it can't be allowed to break routing."""
    mock_db = MagicMock()
    mock_db.commit.side_effect = Exception("db unavailable")
    mock_session_local.return_value = mock_db

    log_routing_decision(str(uuid.uuid4()), _decision(), model_used="groq:llama3-8b-8192")

    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# get_routing_decision
# ---------------------------------------------------------------------------

@patch("services.router.router.audit.SessionLocal")
def test_get_routing_decision_queries_by_job_id_most_recent_first(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    job_id = str(uuid.uuid4())

    get_routing_decision(job_id)

    mock_db.query.assert_called_once()
    mock_db.query.return_value.filter.assert_called_once()
    mock_db.query.return_value.filter.return_value.order_by.assert_called_once()
    mock_db.close.assert_called_once()
