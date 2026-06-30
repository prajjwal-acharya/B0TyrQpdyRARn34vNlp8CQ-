"""Unit tests for the async processing pipeline task chain.

Covers both branch cases:
  - digital PDF  (native text layer present → OCR short-circuited)
  - scanned image (no native text → OpenCV preprocessing + PaddleOCR)

Tasks are exercised via .run() which bypasses the Celery broker and calls the
underlying Python function directly.  Celery-level retry behaviour (exponential
back-off, MaxRetriesExceededError) is tested through helpers rather than the
full Celery machinery.
"""
from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, call, patch

import fitz
import pytest

from services.ingestion.workers.tasks import (
    _backoff,
    _cv_preprocess,
    _dead_letter,
    langdetect_doc,
    mark_ready,
    ocr_bbox,
    preprocess,
    validate_file,
)


# ---------------------------------------------------------------------------
# Fixtures / small helpers
# ---------------------------------------------------------------------------

def _make_doc(
    doc_id: uuid.UUID,
    status: str = "queued",
    minio_key: str = "raw/obj/file.pdf",
    mime_type: str = "application/pdf",
) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.status = status
    doc.minio_key = minio_key
    doc.mime_type = mime_type
    return doc


def _make_db(doc: MagicMock | None = None) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = doc
    return db


def _make_pdf_bytes(text: str = "This is long enough native text for a digital PDF page content.") -> bytes:
    """Minimal single-page PDF with native text layer."""
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _make_png_bytes() -> bytes:
    """Minimal 100×100 white PNG image."""
    import cv2
    import numpy as np

    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    _, buf = cv2.imencode(".png", img)
    return bytes(buf)


# ---------------------------------------------------------------------------
# _backoff — exponential delay helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("retries", "expected"),
    [(0, 60), (1, 120), (2, 240)],
)
def test_backoff(retries: int, expected: int) -> None:
    task = MagicMock()
    task.request.retries = retries
    assert _backoff(task) == expected


# ---------------------------------------------------------------------------
# _cv_preprocess — OpenCV pipeline
# ---------------------------------------------------------------------------

def test_cv_preprocess_returns_png_bytes() -> None:
    result = _cv_preprocess(_make_png_bytes())
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_cv_preprocess_invalid_input_returns_original() -> None:
    bad = b"not-an-image"
    assert _cv_preprocess(bad) == bad


# ---------------------------------------------------------------------------
# _dead_letter — dead-letter handler
# ---------------------------------------------------------------------------

@patch("services.ingestion.workers.tasks._db_update")
def test_dead_letter_marks_document_failed(mock_db_update: MagicMock) -> None:
    doc_id = str(uuid.uuid4())
    exc = ValueError("disk full")
    _dead_letter("preprocess", doc_id, exc)
    mock_db_update.assert_called_once()
    kwargs = mock_db_update.call_args[1]
    assert kwargs["status"] == "failed"
    assert "disk full" in kwargs["error_detail"]


@patch("services.ingestion.workers.tasks._db_update", side_effect=Exception("db down"))
def test_dead_letter_tolerates_db_error(mock_db_update: MagicMock) -> None:
    """_dead_letter must not raise even when the DB update itself fails."""
    _dead_letter("mark_ready", str(uuid.uuid4()), RuntimeError("oops"))
    # No assertion needed — if _dead_letter raises, the test fails


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------

@patch("services.ingestion.workers.tasks.SessionLocal")
@patch("services.ingestion.workers.tasks._get_minio")
@patch("services.ingestion.workers.tasks._db_update")
def test_validate_file_success(
    mock_db_update: MagicMock,
    mock_get_minio: MagicMock,
    mock_session: MagicMock,
) -> None:
    doc_id = str(uuid.uuid4())
    doc = _make_doc(uuid.UUID(doc_id), minio_key="raw/obj/report.pdf")
    mock_session.return_value = _make_db(doc)

    minio = MagicMock()
    mock_get_minio.return_value = minio

    result = validate_file.run(doc_id)

    assert result == doc_id
    minio.stat_object.assert_called_once_with("raw", "obj/report.pdf")
    mock_db_update.assert_called_once_with(doc_id, status="processing")


@patch("services.ingestion.workers.tasks.SessionLocal")
@patch("services.ingestion.workers.tasks._get_minio")
@patch("services.ingestion.workers.tasks._db_update")
def test_validate_file_raises_when_object_missing(
    mock_db_update: MagicMock,
    mock_get_minio: MagicMock,
    mock_session: MagicMock,
) -> None:
    doc_id = str(uuid.uuid4())
    doc = _make_doc(uuid.UUID(doc_id), minio_key="raw/obj/file.pdf")
    mock_session.return_value = _make_db(doc)

    minio = MagicMock()
    minio.stat_object.side_effect = Exception("not found")
    mock_get_minio.return_value = minio

    with pytest.raises(Exception):
        validate_file.run(doc_id)

    # Status must NOT be changed to "processing" when MinIO stat fails
    mock_db_update.assert_not_called()


# ---------------------------------------------------------------------------
# preprocess — digital PDF branch
# ---------------------------------------------------------------------------

@patch("services.ingestion.workers.tasks.SessionLocal")
@patch("services.ingestion.workers.tasks._get_minio")
@patch("services.ingestion.workers.tasks._db_update")
def test_preprocess_digital_pdf_no_ocv(
    mock_db_update: MagicMock,
    mock_get_minio: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Digital PDF pages (≥50 native chars) are flagged is_scanned=False."""
    doc_id = str(uuid.uuid4())
    doc = _make_doc(uuid.UUID(doc_id), minio_key="raw/obj/report.pdf", mime_type="application/pdf")
    mock_session.return_value = _make_db(doc)

    pdf_bytes = _make_pdf_bytes()
    minio = MagicMock()
    minio.get_object.return_value = MagicMock(read=lambda: pdf_bytes)
    minio.bucket_exists.return_value = True
    mock_get_minio.return_value = minio

    result = preprocess.run(doc_id)

    assert result["doc_id"] == doc_id
    assert len(result["pages"]) == 1
    page = result["pages"][0]
    assert page["is_scanned"] is False
    assert len(page["native_text"]) >= 50

    mock_db_update.assert_called_once()
    kwargs = mock_db_update.call_args[1]
    assert kwargs["status"] == "preprocessed"
    assert kwargs["page_count"] == 1


@patch("services.ingestion.workers.tasks.SessionLocal")
@patch("services.ingestion.workers.tasks._get_minio")
@patch("services.ingestion.workers.tasks._db_update")
def test_preprocess_scanned_image_runs_opencv(
    mock_db_update: MagicMock,
    mock_get_minio: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Non-PDF files are treated as single-page scanned images."""
    doc_id = str(uuid.uuid4())
    doc = _make_doc(uuid.UUID(doc_id), minio_key="raw/obj/scan.png", mime_type="image/png")
    mock_session.return_value = _make_db(doc)

    minio = MagicMock()
    minio.get_object.return_value = MagicMock(read=lambda: _make_png_bytes())
    minio.bucket_exists.return_value = True
    mock_get_minio.return_value = minio

    result = preprocess.run(doc_id)

    assert result["doc_id"] == doc_id
    assert len(result["pages"]) == 1
    page = result["pages"][0]
    assert page["is_scanned"] is True
    assert page["native_text"] == ""

    # Preprocessed image must have been stored in MinIO "processed" bucket
    minio.put_object.assert_called_once()
    put_bucket = minio.put_object.call_args[0][0]
    assert put_bucket == "processed"


# ---------------------------------------------------------------------------
# ocr_bbox — digital page short-circuits OCR
# ---------------------------------------------------------------------------

@patch("services.ingestion.workers.tasks._get_minio")
@patch("services.ingestion.workers.tasks._db_update")
def test_ocr_bbox_digital_page_skips_ocr(
    mock_db_update: MagicMock,
    mock_get_minio: MagicMock,
) -> None:
    doc_id = str(uuid.uuid4())
    preprocess_result = {
        "doc_id": doc_id,
        "pages": [
            {
                "page_num": 0,
                "native_text": "This is rich native text content from a digital PDF page.",
                "is_scanned": False,
                "processed_key": "processed/key/page_0.png",
            }
        ],
    }

    with patch("paddleocr.PaddleOCR") as mock_ocr_cls:
        result = ocr_bbox.run(preprocess_result)

    assert result["doc_id"] == doc_id
    assert "0" in result["bbox_data"]
    entry = result["bbox_data"]["0"][0]
    assert entry["source"] == "native"
    assert entry["confidence"] == 1.0
    # PaddleOCR is instantiated but .ocr() is never called for digital pages
    mock_ocr_cls.return_value.ocr.assert_not_called()


@patch("services.ingestion.workers.tasks._get_minio")
@patch("services.ingestion.workers.tasks._db_update")
def test_ocr_bbox_scanned_page_calls_paddleocr(
    mock_db_update: MagicMock,
    mock_get_minio: MagicMock,
) -> None:
    doc_id = str(uuid.uuid4())
    preprocess_result = {
        "doc_id": doc_id,
        "pages": [
            {
                "page_num": 0,
                "native_text": "",
                "is_scanned": True,
                "processed_key": "processed/key/page_0.png",
            }
        ],
    }

    minio = MagicMock()
    minio.get_object.return_value = MagicMock(read=lambda: _make_png_bytes())
    mock_get_minio.return_value = minio

    fake_result = [
        [[[10, 10], [100, 10], [100, 30], [10, 30]], ("Invoice Total", 0.97)]
    ]
    with patch("paddleocr.PaddleOCR") as mock_ocr_cls:
        mock_ocr_cls.return_value.ocr.return_value = [fake_result]
        result = ocr_bbox.run(preprocess_result)

    assert result["doc_id"] == doc_id
    bbox_entries = result["bbox_data"]["0"]
    assert len(bbox_entries) == 1
    entry = bbox_entries[0]
    assert entry["text"] == "Invoice Total"
    assert entry["source"] == "paddleocr"
    assert entry["confidence"] == pytest.approx(0.97)

    mock_db_update.assert_called_once_with(doc_id, bbox_data=result["bbox_data"])


# ---------------------------------------------------------------------------
# langdetect_doc
# ---------------------------------------------------------------------------

@patch("services.ingestion.workers.tasks._db_update")
def test_langdetect_english_text(mock_db_update: MagicMock) -> None:
    doc_id = str(uuid.uuid4())
    ocr_result = {
        "doc_id": doc_id,
        "pages": [{"native_text": "This document contains English text for language detection purposes."}],
        "bbox_data": {},
    }
    result = langdetect_doc.run(ocr_result)
    assert result["doc_id"] == doc_id
    assert result["lang"] == "en"
    mock_db_update.assert_called_once_with(doc_id, lang="en")


@patch("services.ingestion.workers.tasks._db_update")
def test_langdetect_empty_text_returns_unknown(mock_db_update: MagicMock) -> None:
    doc_id = str(uuid.uuid4())
    ocr_result = {
        "doc_id": doc_id,
        "pages": [{"native_text": ""}],
        "bbox_data": {},
    }
    result = langdetect_doc.run(ocr_result)
    assert result["lang"] == "unknown"
    mock_db_update.assert_called_once_with(doc_id, lang="unknown")


@patch("services.ingestion.workers.tasks._db_update")
def test_langdetect_aggregates_bbox_text(mock_db_update: MagicMock) -> None:
    """langdetect uses both native page text and OCR-extracted bbox text."""
    doc_id = str(uuid.uuid4())
    ocr_result = {
        "doc_id": doc_id,
        "pages": [{"native_text": ""}],
        "bbox_data": {
            "0": [
                {"text": "This is text from OCR for language detection.", "source": "paddleocr"}
            ]
        },
    }
    result = langdetect_doc.run(ocr_result)
    assert result["lang"] == "en"


# ---------------------------------------------------------------------------
# mark_ready
# ---------------------------------------------------------------------------

@patch("services.ingestion.workers.tasks._db_update")
def test_mark_ready_transitions_status(mock_db_update: MagicMock) -> None:
    doc_id = str(uuid.uuid4())
    result = mark_ready.run({"doc_id": doc_id, "lang": "en"})
    assert result["doc_id"] == doc_id
    assert result["status"] == "ready_for_routing"
    mock_db_update.assert_called_once_with(doc_id, status="ready_for_routing")
