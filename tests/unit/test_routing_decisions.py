"""Unit tests for GET /routing-decisions/{job_id} (Phase 12 — Audit log query).

Deliverable under test: querying the log table for any job_id returns the
full routing rationale (doc_type, confidence, model_used, reasoning, timestamp).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.ingestion.api.main import app
from shared.db import get_db


@pytest.fixture
def client():
    return TestClient(app)


def _make_decision_row(job_id: uuid.UUID) -> MagicMock:
    row = MagicMock()
    row.job_id = job_id
    row.doc_type = "passport"
    row.confidence = 0.95
    row.model_used = "groq:llama3-8b-8192"
    row.reasoning = "has photo page and MRZ"
    row.fallback_used = False
    row.created_at = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    return row


def _make_db(decision_row=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
        decision_row
    )
    return db


def test_get_routing_decision_returns_full_rationale(client):
    job_id = uuid.uuid4()
    app.dependency_overrides[get_db] = lambda: _make_db(_make_decision_row(job_id))

    try:
        resp = client.get(f"/routing-decisions/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == str(job_id)
        assert body["doc_type"] == "passport"
        assert body["confidence"] == pytest.approx(0.95)
        assert body["model_used"] == "groq:llama3-8b-8192"
        assert body["reasoning"] == "has photo page and MRZ"
        assert body["fallback_used"] is False
        assert body["timestamp"] == "2026-06-30T12:00:00+00:00"
    finally:
        app.dependency_overrides.clear()


def test_get_routing_decision_404_when_not_logged(client):
    job_id = uuid.uuid4()
    app.dependency_overrides[get_db] = lambda: _make_db(decision_row=None)

    try:
        resp = client.get(f"/routing-decisions/{job_id}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_routing_decision_404_invalid_uuid(client):
    app.dependency_overrides[get_db] = lambda: _make_db()

    try:
        resp = client.get("/routing-decisions/not-a-uuid")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
