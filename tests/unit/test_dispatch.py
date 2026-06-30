"""Unit tests for Phase 2B conditional dispatch.

Tests cover:
- route_by_doc_type: pure routing-function behavior (decision -> node name)
- fallback_review: flags manual review without picking a doc-type subgraph
- Full router_graph.invoke(): classify -> conditional dispatch -> correct
  stub subgraph per doc type, and an explicit (non-silent) fallback branch
  for low-confidence classifications.

All LLM calls and MinIO I/O are mocked — no network access required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.router.router.fallback import FALLBACK_NODE, fallback_review
from services.router.router.graph import (
    LOW_CONFIDENCE_THRESHOLD,
    _DOC_TYPE_SUBGRAPHS,
    build_router_graph,
    route_by_doc_type,
)
from services.router.router.node import _LLMDecision
from services.router.router.schemas import DocType, RouterDecision, RouterState
from shared.contracts import BBoxEntry, JobMetadata, P1OutputPayload, PageImage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_metadata(filename: str = "doc.pdf") -> JobMetadata:
    now = datetime.now(tz=timezone.utc)
    return JobMetadata(
        filename=filename,
        mime_type="application/pdf",
        page_count=1,
        file_hash="abc123",
        created_at=now,
        updated_at=now,
    )


def _make_payload(text_entries: list[str], filename: str = "doc.pdf") -> P1OutputPayload:
    job_id = str(uuid.uuid4())
    bbox = [BBoxEntry(text=t, bbox=None, confidence=1.0, source="native") for t in text_entries]
    return P1OutputPayload(
        job_id=job_id,
        page_images=[PageImage(page_num=0, minio_key=f"processed/{job_id}/page_0.png")],
        bbox_data={"0": bbox},
        detected_lang="en",
        native_text_layer=None,
        metadata=_make_metadata(filename),
    )


def _mock_chat(doc_type: DocType, confidence: float) -> MagicMock:
    """Return a mock that patches a Chat* class and returns the given decision."""
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = _LLMDecision(
        doc_type=doc_type, confidence=confidence, reasoning="mock"
    )
    mock_cls = MagicMock()
    mock_cls.return_value.with_structured_output.return_value = mock_chain
    return mock_cls


@pytest.fixture(autouse=True)
def _mock_audit_log():
    """Routing-decision audit logging hits Postgres — stub it out for unit tests."""
    with patch("services.router.router.node.log_routing_decision") as mock_log:
        yield mock_log


# ---------------------------------------------------------------------------
# route_by_doc_type — pure routing function
# ---------------------------------------------------------------------------

def test_route_by_doc_type_no_decision_goes_to_fallback():
    state: RouterState = {"p1_payload": _make_payload(["x"]), "decision": None}
    assert route_by_doc_type(state) == FALLBACK_NODE


def test_route_by_doc_type_low_confidence_goes_to_fallback():
    decision = RouterDecision(
        doc_type=DocType.PASSPORT, confidence=LOW_CONFIDENCE_THRESHOLD - 0.01, reasoning="x"
    )
    state: RouterState = {"p1_payload": _make_payload(["x"]), "decision": decision}
    assert route_by_doc_type(state) == FALLBACK_NODE


def test_route_by_doc_type_at_threshold_dispatches_normally():
    """Confidence == threshold should NOT hit the fallback branch."""
    decision = RouterDecision(
        doc_type=DocType.GST, confidence=LOW_CONFIDENCE_THRESHOLD, reasoning="x"
    )
    state: RouterState = {"p1_payload": _make_payload(["x"]), "decision": decision}
    assert route_by_doc_type(state) == "gst"


@pytest.mark.parametrize("doc_type", list(DocType))
def test_route_by_doc_type_confident_dispatches_to_matching_node(doc_type: DocType):
    decision = RouterDecision(doc_type=doc_type, confidence=0.9, reasoning="x")
    state: RouterState = {"p1_payload": _make_payload(["x"]), "decision": decision}
    expected_node, _ = _DOC_TYPE_SUBGRAPHS[doc_type]
    assert route_by_doc_type(state) == expected_node


# ---------------------------------------------------------------------------
# fallback_review node
# ---------------------------------------------------------------------------

def test_fallback_review_flags_manual_review_without_decision():
    state: RouterState = {"p1_payload": _make_payload(["x"]), "decision": None}
    result = fallback_review(state)
    assert result["needs_manual_review"] is True
    assert result["dispatched_to"] is None


def test_fallback_review_flags_manual_review_with_low_confidence_decision():
    decision = RouterDecision(doc_type=DocType.GST, confidence=0.2, reasoning="unsure")
    state: RouterState = {"p1_payload": _make_payload(["x"]), "decision": decision}
    result = fallback_review(state)
    assert result["needs_manual_review"] is True
    assert result["dispatched_to"] is None


# ---------------------------------------------------------------------------
# Full graph: classify -> conditional dispatch -> stub subgraph / fallback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("doc_type", list(DocType))
def test_full_graph_dispatches_to_correct_subgraph(doc_type: DocType):
    with (
        patch("services.router.router.node.ChatGroq", _mock_chat(doc_type, 0.95)),
        patch("services.router.router.node.ChatGoogleGenerativeAI") as mock_gemini,
    ):
        graph = build_router_graph()
        result = graph.invoke({"p1_payload": _make_payload(["sample text"]), "decision": None})
        mock_gemini.assert_not_called()

    assert result["dispatched_to"] == doc_type.value
    assert not result.get("needs_manual_review")


def test_full_graph_low_confidence_hits_fallback_not_silent_default():
    """Even after the Groq -> Gemini escalation, a still-low confidence must
    visibly hit the fallback branch instead of dispatching into a doc-type
    subgraph it might not actually belong to."""
    with (
        patch("services.router.router.node.ChatGroq", _mock_chat(DocType.ITR, 0.3)),
        patch("services.router.router.node.ChatGoogleGenerativeAI", _mock_chat(DocType.ITR, 0.4)),
        patch("services.router.router.node._get_minio") as mock_get_minio,
    ):
        mock_minio = MagicMock()
        mock_minio.get_object.return_value = MagicMock(read=lambda: b"fake-image-bytes")
        mock_get_minio.return_value = mock_minio

        graph = build_router_graph()
        result = graph.invoke(
            {"p1_payload": _make_payload(["ambiguous text"]), "decision": None}
        )

    assert result["needs_manual_review"] is True
    assert result["dispatched_to"] is None
    assert result["decision"].doc_type == DocType.ITR  # decision is preserved for review tooling
