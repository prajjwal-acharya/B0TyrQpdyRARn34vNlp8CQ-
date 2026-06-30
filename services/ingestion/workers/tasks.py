"""Async processing pipeline task chain.

Chain: validate_file → preprocess → ocr_bbox → langdetect_doc → mark_ready

Status transitions:
  queued       → processing        (validate_file)
  processing   → preprocessed      (preprocess)
  preprocessed → ready_for_routing (mark_ready)
  any step     → failed            (on max_retries exceeded — dead-letter)

Retry policy: max 3 attempts, exponential backoff (60s → 120s → 240s).
Dead-letter: on exhaustion, document status is set to "failed" and the error
is persisted to error_detail; a DEAD_LETTER log line marks it for alerting.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

import cv2
import fitz  # PyMuPDF
import numpy as np
from langdetect import LangDetectException, detect

try:
    from pipeline.celery_app import celery_app  # container context (/app/pipeline/)
except ImportError:
    from services.ingestion.pipeline.celery_app import celery_app  # type: ignore[no-redef]

from shared.config import settings
from shared.db import SessionLocal
from shared.models import Document

logger = logging.getLogger(__name__)

_PROCESSED_BUCKET = "processed"

_TASK_DEFAULTS: dict[str, Any] = {
    "acks_late": True,
    "reject_on_worker_lost": True,
    "max_retries": 3,
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_minio() -> Any:
    from minio import Minio

    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _ensure_bucket(client: Any, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _db_update(doc_id: str, **fields: Any) -> None:
    """Atomically update Document fields in a short-lived session."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None:
            raise ValueError(f"Document {doc_id} not found")
        for k, v in fields.items():
            setattr(doc, k, v)
        doc.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _backoff(task: Any, base: int = 60) -> int:
    """Exponential backoff countdown in seconds: 60, 120, 240."""
    return base * (2 ** task.request.retries)


def _dead_letter(task_name: str, doc_id: str, exc: Exception) -> None:
    """Mark document failed and emit a DEAD_LETTER log for alerting."""
    logger.error(
        "DEAD_LETTER task=%s doc=%s error=%s",
        task_name,
        doc_id,
        exc,
        exc_info=True,
    )
    try:
        _db_update(doc_id, status="failed", error_detail=str(exc)[:1000])
    except Exception:
        logger.exception("Could not mark doc=%s as failed after dead-letter", doc_id)


# ---------------------------------------------------------------------------
# OpenCV image preprocessing (scanned / photo docs only)
# ---------------------------------------------------------------------------

def _deskew(gray: np.ndarray) -> np.ndarray:
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    coords = np.column_stack(np.where(edges > 0))
    if len(coords) < 5:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape
    center = (w // 2, h // 2)
    rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray, rot_matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _cv_preprocess(image_bytes: bytes) -> bytes:
    """Deskew, denoise, and CLAHE contrast-normalise a scanned/photo page."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = _deskew(gray)
    _, buf = cv2.imencode(".png", gray)
    return bytes(buf)


# ---------------------------------------------------------------------------
# Task 1 — validate_file
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="pipeline.validate_file", **_TASK_DEFAULTS)
def validate_file(self: Any, doc_id: str) -> str:
    """Verify file exists in MinIO; transition queued → processing."""
    try:
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc is None:
                raise ValueError(f"Document {doc_id} not found in database")
            minio_key = doc.minio_key or ""
        finally:
            db.close()

        bucket, _, obj = minio_key.partition("/")
        _get_minio().stat_object(bucket, obj)
        _db_update(doc_id, status="processing")
        logger.info("validate_file OK doc=%s", doc_id)
        return doc_id

    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=_backoff(self))
        except self.MaxRetriesExceededError:
            _dead_letter("validate_file", doc_id, exc)
            raise


# ---------------------------------------------------------------------------
# Task 2 — preprocess
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="pipeline.preprocess", **_TASK_DEFAULTS)
def preprocess(self: Any, doc_id: str) -> dict:
    """Split pages; extract native text (digital PDF) or run OpenCV (scanned).

    Preprocessed page images are stored in MinIO under the 'processed' bucket
    so downstream tasks can fetch them without passing large blobs via Redis.
    """
    try:
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc is None:
                raise ValueError(f"Document {doc_id} not found")
            minio_key = doc.minio_key or ""
            mime_type = doc.mime_type or ""
        finally:
            db.close()

        bucket, _, obj = minio_key.partition("/")
        client = _get_minio()
        data = client.get_object(bucket, obj).read()
        _ensure_bucket(client, _PROCESSED_BUCKET)

        pages: list[dict] = []
        is_pdf = mime_type == "application/pdf" or obj.lower().endswith(".pdf")

        if is_pdf:
            pdf_doc = fitz.open(stream=data, filetype="pdf")
            for page_num, page in enumerate(pdf_doc):
                native_text = page.get_text().strip()
                # Heuristic: fewer than 50 chars of native text → treat as scanned
                is_scanned = len(native_text) < 50
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                if is_scanned:
                    img_bytes = _cv_preprocess(img_bytes)
                page_key = f"{doc_id}/page_{page_num}.png"
                client.put_object(
                    _PROCESSED_BUCKET,
                    page_key,
                    io.BytesIO(img_bytes),
                    len(img_bytes),
                    content_type="image/png",
                )
                pages.append(
                    {
                        "page_num": page_num,
                        "native_text": native_text,
                        "is_scanned": is_scanned,
                        "processed_key": f"{_PROCESSED_BUCKET}/{page_key}",
                    }
                )
            pdf_doc.close()
        else:
            # Single-page scanned image
            img_bytes = _cv_preprocess(data)
            page_key = f"{doc_id}/page_0.png"
            client.put_object(
                _PROCESSED_BUCKET,
                page_key,
                io.BytesIO(img_bytes),
                len(img_bytes),
                content_type="image/png",
            )
            pages.append(
                {
                    "page_num": 0,
                    "native_text": "",
                    "is_scanned": True,
                    "processed_key": f"{_PROCESSED_BUCKET}/{page_key}",
                }
            )

        _db_update(doc_id, status="preprocessed", page_count=len(pages))
        logger.info("preprocess OK doc=%s pages=%d", doc_id, len(pages))
        return {"doc_id": doc_id, "pages": pages}

    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=_backoff(self))
        except self.MaxRetriesExceededError:
            _dead_letter("preprocess", doc_id, exc)
            raise


# ---------------------------------------------------------------------------
# Task 3 — ocr_bbox
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="pipeline.ocr_bbox", **_TASK_DEFAULTS)
def ocr_bbox(self: Any, preprocess_result: dict) -> dict:
    """Run PaddleOCR on scanned pages; digital pages short-circuit via native text.

    Returns bbox_data: {page_num_str: [{text, bbox, confidence, source}]}
    """
    from paddleocr import PaddleOCR  # heavy import — deferred to task body

    doc_id = preprocess_result["doc_id"]
    pages = preprocess_result["pages"]

    try:
        ocr_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        client = _get_minio()
        bbox_data: dict[str, list] = {}

        for page in pages:
            page_key = str(page["page_num"])
            native_text = page.get("native_text", "")

            if not page["is_scanned"] and native_text:
                # Digital PDF page — skip OCR, use native text as single region
                bbox_data[page_key] = [
                    {"text": native_text, "bbox": None, "confidence": 1.0, "source": "native"}
                ]
                continue

            # Scanned page — fetch preprocessed image and run PaddleOCR
            pk = page["processed_key"]
            bucket, _, obj = pk.partition("/")
            img_bytes = client.get_object(bucket, obj).read()
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                bbox_data[page_key] = []
                continue

            result = ocr_engine.ocr(img, cls=True)
            page_bboxes: list[dict] = []
            if result and result[0]:
                for line in result[0]:
                    coords, (text, confidence) = line
                    page_bboxes.append(
                        {
                            "text": text,
                            "bbox": coords,  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                            "confidence": float(confidence),
                            "source": "paddleocr",
                        }
                    )
            bbox_data[page_key] = page_bboxes

        _db_update(doc_id, bbox_data=bbox_data)
        logger.info("ocr_bbox OK doc=%s pages=%d", doc_id, len(pages))
        return {"doc_id": doc_id, "pages": pages, "bbox_data": bbox_data}

    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=_backoff(self))
        except self.MaxRetriesExceededError:
            _dead_letter("ocr_bbox", doc_id, exc)
            raise


# ---------------------------------------------------------------------------
# Task 4 — langdetect_doc
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="pipeline.langdetect_doc", **_TASK_DEFAULTS)
def langdetect_doc(self: Any, ocr_result: dict) -> dict:
    """Detect document language from aggregated page text; persist lang tag."""
    doc_id = ocr_result["doc_id"]
    try:
        pages = ocr_result["pages"]
        bbox_data = ocr_result.get("bbox_data", {})

        text_parts: list[str] = []
        for page in pages:
            if page.get("native_text"):
                text_parts.append(page["native_text"])
        for page_bboxes in bbox_data.values():
            for item in page_bboxes:
                if item.get("text"):
                    text_parts.append(item["text"])

        combined = " ".join(text_parts)[:3000]
        lang = "unknown"
        if combined.strip():
            try:
                lang = detect(combined)
            except LangDetectException:
                lang = "unknown"

        _db_update(doc_id, lang=lang)
        logger.info("langdetect_doc OK doc=%s lang=%s", doc_id, lang)
        return {"doc_id": doc_id, "lang": lang}

    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=_backoff(self))
        except self.MaxRetriesExceededError:
            _dead_letter("langdetect_doc", doc_id, exc)
            raise


# ---------------------------------------------------------------------------
# Task 5 — mark_ready
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="pipeline.mark_ready", **_TASK_DEFAULTS)
def mark_ready(self: Any, langdetect_result: dict) -> dict:
    """Final status transition: preprocessed → ready_for_routing."""
    doc_id = langdetect_result["doc_id"]
    try:
        _db_update(doc_id, status="ready_for_routing")
        logger.info("mark_ready OK doc=%s", doc_id)
        return {"doc_id": doc_id, "status": "ready_for_routing"}
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=_backoff(self))
        except self.MaxRetriesExceededError:
            _dead_letter("mark_ready", doc_id, exc)
            raise
