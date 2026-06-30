"""Unit tests for the Phase 2 classification node.

Tests cover:
- RouterDecision Pydantic schema validation
- _build_text_context helper
- Groq fast-path (confidence ≥ threshold → no Gemini call)
- Gemini fallback (confidence < threshold → Gemini called with image)
- Gemini fallback with missing image (MinIO error)
- classify_document node for each supported doc type

All LLM calls and MinIO I/O are mocked.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.router.router.node import (
    GROQ_CONFIDENCE_THRESHOLD,
    _LLMDecision,
    _build_text_context,
    classify_document,
)
from services.router.router.schemas import DocType, RouterDecision
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


def _make_payload(
    text_entries: list[str],
    filename: str = "doc.pdf",
    lang: str = "en",
    native_text: str | None = None,
) -> P1OutputPayload:
    job_id = str(uuid.uuid4())
    bbox = [
        BBoxEntry(text=t, bbox=None, confidence=1.0, source="native")
        for t in text_entries
    ]
    native_layer = {"0": native_text} if native_text else None
    return P1OutputPayload(
        job_id=job_id,
        page_images=[PageImage(page_num=0, minio_key=f"processed/{job_id}/page_0.png")],
        bbox_data={"0": bbox},
        detected_lang=lang,
        native_text_layer=native_layer,
        metadata=_make_metadata(filename),
    )


def _make_state(payload: P1OutputPayload) -> dict:
    return {"p1_payload": payload, "decision": None}


def _mock_groq(doc_type: DocType, confidence: float, reasoning: str = "mock") -> MagicMock:
    """Return a mock that patches ChatGroq and returns the given LLM decision."""
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = _LLMDecision(
        doc_type=doc_type, confidence=confidence, reasoning=reasoning
    )

    mock_cls = MagicMock()
    mock_cls.return_value.with_structured_output.return_value = mock_chain
    return mock_cls


def _mock_gemini(doc_type: DocType, confidence: float, reasoning: str = "mock") -> MagicMock:
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = _LLMDecision(
        doc_type=doc_type, confidence=confidence, reasoning=reasoning
    )

    mock_cls = MagicMock()
    mock_cls.return_value.with_structured_output.return_value = mock_chain
    return mock_cls


# ---------------------------------------------------------------------------
# RouterDecision schema
# ---------------------------------------------------------------------------

def test_router_decision_defaults():
    d = RouterDecision(doc_type=DocType.PASSPORT, confidence=0.9, reasoning="looks like passport")
    assert d.fallback_used is False


def test_router_decision_confidence_bounds():
    with pytest.raises(Exception):
        RouterDecision(doc_type=DocType.ITR, confidence=1.5, reasoning="x")

    with pytest.raises(Exception):
        RouterDecision(doc_type=DocType.ITR, confidence=-0.1, reasoning="x")


def test_router_decision_all_doc_types():
    for dt in DocType:
        d = RouterDecision(doc_type=dt, confidence=0.8, reasoning="test")
        assert d.doc_type == dt


def test_router_decision_serialization():
    d = RouterDecision(
        doc_type=DocType.BANK_STATEMENT,
        confidence=0.92,
        reasoning="transaction history",
        fallback_used=True,
    )
    data = d.model_dump()
    assert data["doc_type"] == "bank_statement"
    assert data["fallback_used"] is True
    assert data["confidence"] == pytest.approx(0.92)


# ---------------------------------------------------------------------------
# _build_text_context
# ---------------------------------------------------------------------------

def test_build_text_context_includes_filename():
    payload = _make_payload(["Passport No: A1234567"], filename="passport.pdf")
    ctx = _build_text_context(payload)
    assert "passport.pdf" in ctx


def test_build_text_context_includes_language():
    payload = _make_payload(["some text"], lang="hi")
    ctx = _build_text_context(payload)
    assert "hi" in ctx


def test_build_text_context_includes_bbox_text():
    payload = _make_payload(["Account Statement", "Opening Balance: 10000"])
    ctx = _build_text_context(payload)
    assert "Account Statement" in ctx
    assert "Opening Balance" in ctx


def test_build_text_context_includes_native_text():
    payload = _make_payload([], native_text="Income Tax Return Assessment Year 2024-25")
    ctx = _build_text_context(payload)
    assert "Income Tax Return" in ctx


def test_build_text_context_empty_bbox():
    payload = _make_payload([])
    ctx = _build_text_context(payload)
    assert "Filename:" in ctx  # metadata still present


def test_build_text_context_caps_long_text():
    long_text = "word " * 1000  # ~5000 chars
    payload = _make_payload([long_text])
    ctx = _build_text_context(payload)
    # Should be capped; the context string should not be gigantic
    assert len(ctx) < 5000


# ---------------------------------------------------------------------------
# Groq fast-path
# ---------------------------------------------------------------------------

@patch("services.router.router.node.ChatGroq", _mock_groq(DocType.PASSPORT, 0.95, "has photo page and MRZ"))
def test_groq_fast_path_returns_without_gemini():
    payload = _make_payload(["Passport No: A1234567", "Date of Issue"], filename="passport.pdf")
    state = _make_state(payload)

    with patch("services.router.router.node.ChatGoogleGenerativeAI") as mock_gemini:
        result = classify_document(state)
        mock_gemini.assert_not_called()  # Gemini must NOT be called

    assert result["decision"].doc_type == DocType.PASSPORT
    assert result["decision"].confidence == pytest.approx(0.95)
    assert result["decision"].fallback_used is False


@patch("services.router.router.node.ChatGroq", _mock_groq(DocType.BANK_STATEMENT, 0.90))
def test_groq_fast_path_exact_threshold():
    """Confidence == threshold should also take the fast path."""
    payload = _make_payload(["Account Statement"])
    state = _make_state(payload)

    # Patch threshold to exactly match confidence
    with (
        patch("services.router.router.node.GROQ_CONFIDENCE_THRESHOLD", 0.90),
        patch("services.router.router.node.ChatGoogleGenerativeAI") as mock_gemini,
    ):
        result = classify_document(state)
        mock_gemini.assert_not_called()

    assert result["decision"].fallback_used is False


# ---------------------------------------------------------------------------
# Gemini fallback
# ---------------------------------------------------------------------------

@patch("services.router.router.node.ChatGroq", _mock_groq(DocType.ITR, 0.60, "possibly ITR"))
@patch("services.router.router.node.ChatGoogleGenerativeAI", _mock_gemini(DocType.ITR, 0.94, "ITR with AY and PAN"))
@patch("services.router.router.node._get_minio")
def test_gemini_fallback_called_when_groq_not_confident(mock_get_minio):
    mock_minio = MagicMock()
    mock_minio.get_object.return_value = MagicMock(read=lambda: b"fake-image-bytes")
    mock_get_minio.return_value = mock_minio

    payload = _make_payload(["Assessment Year 2024-25"], filename="itr.pdf")
    state = _make_state(payload)

    result = classify_document(state)

    assert result["decision"].doc_type == DocType.ITR
    assert result["decision"].fallback_used is True
    assert result["decision"].confidence == pytest.approx(0.94)
    mock_minio.get_object.assert_called_once()


@patch("services.router.router.node.ChatGroq", _mock_groq(DocType.FORM_16, 0.70))
@patch("services.router.router.node.ChatGoogleGenerativeAI", _mock_gemini(DocType.FORM_16, 0.88))
@patch("services.router.router.node._get_minio")
def test_gemini_fallback_tolerates_minio_error(mock_get_minio):
    """Gemini should still be called even when the image fetch fails."""
    mock_minio = MagicMock()
    mock_minio.get_object.side_effect = Exception("minio unavailable")
    mock_get_minio.return_value = mock_minio

    payload = _make_payload(["Employer: Acme Corp"], filename="form16.pdf")
    state = _make_state(payload)

    result = classify_document(state)

    # Decision is still returned (Gemini called without image)
    assert result["decision"].fallback_used is True
    assert result["decision"].doc_type == DocType.FORM_16


# ---------------------------------------------------------------------------
# Per-doc-type smoke tests (Groq fast-path)
# ---------------------------------------------------------------------------

_DOC_FIXTURES: list[tuple[DocType, list[str], str]] = [
    (
        DocType.PASSPORT,
        ["Passport No: A1234567", "Date of Birth", "Nationality: Indian", "MRZ"],
        "passport.pdf",
    ),
    (
        DocType.BANK_STATEMENT,
        ["Account Statement", "Opening Balance", "Closing Balance", "IFSC: HDFC0001234"],
        "bank_statement.pdf",
    ),
    (
        DocType.ITR,
        ["Income Tax Return", "Assessment Year: 2024-25", "PAN:", "Gross Total Income"],
        "itr_ay2425.pdf",
    ),
    (
        DocType.FORM_16,
        ["Certificate under section 203", "Tax Deducted at Source", "Employer Name"],
        "form16.pdf",
    ),
    (
        DocType.SALARY_SLIP,
        ["Pay Slip", "Basic Salary", "HRA", "PF Deduction", "Net Pay"],
        "salary_slip_march.pdf",
    ),
    (
        DocType.GST,
        ["GSTIN:", "Goods and Services Tax", "Registration Certificate"],
        "gst_certificate.pdf",
    ),
    (
        DocType.PROPERTY_DEED,
        ["Sale Deed", "Vendor", "Purchaser", "Schedule of Property", "Sub-Registrar"],
        "property_deed.pdf",
    ),
]


@pytest.mark.parametrize("doc_type,texts,filename", _DOC_FIXTURES)
def test_classify_document_per_doc_type(doc_type: DocType, texts: list[str], filename: str):
    mock_groq = _mock_groq(doc_type, 0.95, f"classified as {doc_type.value}")

    with (
        patch("services.router.router.node.ChatGroq", mock_groq),
        patch("services.router.router.node.ChatGoogleGenerativeAI") as mock_gemini_cls,
    ):
        payload = _make_payload(texts, filename=filename)
        result = classify_document(_make_state(payload))

    assert result["decision"].doc_type == doc_type
    assert result["decision"].fallback_used is False
    mock_gemini_cls.assert_not_called()


# ---------------------------------------------------------------------------
# RouterDecision model_validate round-trip
# ---------------------------------------------------------------------------

def test_router_decision_round_trip():
    original = RouterDecision(
        doc_type=DocType.SALARY_SLIP,
        confidence=0.88,
        reasoning="monthly pay slip with deductions",
        fallback_used=True,
    )
    restored = RouterDecision.model_validate(original.model_dump())
    assert restored == original
