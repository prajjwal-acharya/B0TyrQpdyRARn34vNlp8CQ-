import hashlib
import io
import logging
import uuid

import imagehash
from celery import chain as celery_chain
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from minio import Minio
from minio.error import S3Error
from PIL import Image
from sqlalchemy.orm import Session

from shared.config import settings
from shared.contracts import (
    BBoxEntry,
    ErrorCode,
    JobMetadata,
    P1ErrorPayload,
    P1OutputPayload,
    P1PendingPayload,
    PageImage,
)
from shared.db import get_db
from shared.models import Document, RoutingDecision

try:
    from pipeline.celery_app import celery_app  # container context (/app/pipeline/)
except ImportError:
    from services.ingestion.pipeline.celery_app import celery_app  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

app = FastAPI(title="Adaptive Doc Intelligence API", version="0.1.0")

_RAW_BUCKET = "raw"


def _get_minio() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _compute_file_hash(data: bytes, mime_type: str) -> str:
    """Perceptual hash for images (imagehash.phash); SHA-256 for everything else."""
    if mime_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(data))
            return str(imagehash.phash(img))
        except Exception:
            pass
    return hashlib.sha256(data).hexdigest()


def _dispatch_pipeline(job_id: uuid.UUID) -> None:
    """Enqueue the full processing chain for a newly uploaded document."""
    try:
        celery_chain(
            celery_app.signature("pipeline.validate_file", args=[str(job_id)]),
            celery_app.signature("pipeline.preprocess"),
            celery_app.signature("pipeline.ocr_bbox"),
            celery_app.signature("pipeline.langdetect_doc"),
            celery_app.signature("pipeline.mark_ready"),
        ).apply_async()
    except Exception:
        logger.exception("Failed to dispatch pipeline for job_id=%s — document remains queued", job_id)


_PENDING_STATUSES = {"queued", "processing", "preprocessed"}

_ERROR_KEYWORD_MAP: list[tuple[str, ErrorCode]] = [
    ("corrupt", ErrorCode.CORRUPT_FILE),
    ("invalid", ErrorCode.CORRUPT_FILE),
    ("unsupported", ErrorCode.UNSUPPORTED_FORMAT),
    ("format", ErrorCode.UNSUPPORTED_FORMAT),
    ("ocr", ErrorCode.OCR_FAILURE),
    ("paddle", ErrorCode.OCR_FAILURE),
    ("timeout", ErrorCode.TIMEOUT),
    ("timed out", ErrorCode.TIMEOUT),
]


def _infer_error_code(error_detail: str | None) -> ErrorCode:
    if not error_detail:
        return ErrorCode.UNKNOWN
    lower = error_detail.lower()
    for keyword, code in _ERROR_KEYWORD_MAP:
        if keyword in lower:
            return code
    return ErrorCode.UNKNOWN


def _job_metadata(doc: Document) -> JobMetadata:
    return JobMetadata(
        filename=doc.filename,
        mime_type=doc.mime_type,
        page_count=doc.page_count or 1,
        file_hash=doc.file_hash,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _build_output_payload(doc: Document) -> P1OutputPayload:
    page_count = doc.page_count or 1
    bbox_raw: dict = doc.bbox_data or {}

    page_images = [
        PageImage(page_num=n, minio_key=f"processed/{doc.id}/page_{n}.png")
        for n in range(page_count)
    ]

    bbox_data: dict[str, list[BBoxEntry]] = {}
    native_text_layer: dict[str, str] = {}
    for page_num_str, entries in bbox_raw.items():
        parsed = [BBoxEntry(**e) for e in entries]
        bbox_data[page_num_str] = parsed
        if entries and entries[0].get("source") == "native":
            native_text_layer[page_num_str] = entries[0]["text"]

    return P1OutputPayload(
        job_id=str(doc.id),
        page_images=page_images,
        bbox_data=bbox_data,
        detected_lang=doc.lang or "unknown",
        native_text_layer=native_text_layer or None,
        metadata=_job_metadata(doc),
    )


def _build_error_payload(doc: Document) -> P1ErrorPayload:
    return P1ErrorPayload(
        job_id=str(doc.id),
        error_code=_infer_error_code(doc.error_detail),
        error_detail=doc.error_detail,
        metadata=_job_metadata(doc),
    )


@app.get(
    "/jobs/{job_id}",
    responses={
        200: {"description": "Job complete — ready_for_routing or failed"},
        202: {"description": "Job still processing — poll again"},
        404: {"description": "Job not found"},
    },
)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    """Return the P1 output payload for a document job.

    * **ready_for_routing** → HTTP 200, P1OutputPayload — safe for P2 to route.
    * **failed** → HTTP 200, P1ErrorPayload — P2 must not route; inspect error_code.
    * **queued / processing / preprocessed** → HTTP 202, P1PendingPayload — poll again.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid job_id format")

    doc = db.query(Document).filter(Document.id == job_uuid).first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if doc.status == "ready_for_routing":
        payload = _build_output_payload(doc)
        return JSONResponse(content=payload.model_dump(mode="json"))

    if doc.status == "failed":
        payload = _build_error_payload(doc)
        return JSONResponse(content=payload.model_dump(mode="json"))

    if doc.status in _PENDING_STATUSES:
        pending = P1PendingPayload(
            job_id=str(doc.id),
            status=doc.status,  # type: ignore[arg-type]
            metadata=_job_metadata(doc),
        )
        return JSONResponse(status_code=202, content=pending.model_dump(mode="json"))

    raise HTTPException(status_code=500, detail=f"Unexpected job status: {doc.status!r}")


@app.get(
    "/routing-decisions/{job_id}",
    responses={404: {"description": "No routing decision logged for this job_id"}},
)
def get_routing_decision(job_id: str, db: Session = Depends(get_db)) -> dict:
    """Return the full routing rationale logged for a job_id (Phase 12 — Audit log).

    Backs the MoE-router demo Q&A: every routing decision is traceable back
    to which model decided, at what confidence, and why.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid job_id format")

    decision = (
        db.query(RoutingDecision)
        .filter(RoutingDecision.job_id == job_uuid)
        .order_by(RoutingDecision.created_at.desc())
        .first()
    )
    if decision is None:
        raise HTTPException(
            status_code=404, detail=f"No routing decision logged for job {job_id}"
        )

    return {
        "job_id": str(decision.job_id),
        "doc_type": decision.doc_type,
        "confidence": decision.confidence,
        "model_used": decision.model_used,
        "reasoning": decision.reasoning,
        "fallback_used": decision.fallback_used,
        "timestamp": decision.created_at.isoformat(),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    data = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    file_hash = _compute_file_hash(data, mime_type)

    # Idempotency: return existing job_id without re-storing
    existing = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing:
        return {"job_id": str(existing.id), "deduplicated": True}

    job_id = uuid.uuid4()
    object_name = f"{job_id}/{file.filename}"
    minio_key = f"{_RAW_BUCKET}/{object_name}"

    client = _get_minio()
    _ensure_bucket(client, _RAW_BUCKET)
    try:
        client.put_object(
            _RAW_BUCKET,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=mime_type,
        )
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"Storage error: {exc}") from exc

    doc = Document(
        id=job_id,
        filename=file.filename or "unknown",
        file_hash=file_hash,
        mime_type=mime_type,
        minio_key=minio_key,
        status="queued",
    )
    db.add(doc)
    db.commit()

    _dispatch_pipeline(job_id)

    return {"job_id": str(job_id), "deduplicated": False}
