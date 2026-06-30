"""P1 → P2 Output Contract — schema version 1.0.

Versioned Pydantic v2 models locking the exact payload P2 (Router) consumes
once a document completes the P1 ingestion pipeline.

Status flow:
  queued → processing → preprocessed → ready_for_routing
                                      ↘ failed

P2 MUST only route documents with status == "ready_for_routing".
Documents with status == "failed" carry an ErrorCode that explains why.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class ErrorCode(str, Enum):
    """Reason codes surfaced when status == "failed"."""

    CORRUPT_FILE = "corrupt_file"
    UNSUPPORTED_FORMAT = "unsupported_format"
    OCR_FAILURE = "ocr_failure"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class BBoxEntry(BaseModel):
    """Single text region detected by OCR or extracted from a native PDF layer."""

    text: str
    bbox: list[list[float]] | None = None  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]; None for native
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["paddleocr", "native"]


class PageImage(BaseModel):
    """Reference to a preprocessed page image stored in MinIO."""

    page_num: int = Field(ge=0)
    minio_key: str  # e.g. "processed/{job_id}/page_0.png"


class JobMetadata(BaseModel):
    """Immutable document-level metadata."""

    filename: str
    mime_type: str | None
    page_count: int = Field(ge=1)
    file_hash: str
    created_at: datetime
    updated_at: datetime


class P1OutputPayload(BaseModel):
    """Payload P2 receives for a successfully processed document.

    All fields guaranteed present; P2 should never see partial data.
    """

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    job_id: str
    status: Literal["ready_for_routing"] = "ready_for_routing"
    page_images: list[PageImage]
    bbox_data: dict[str, list[BBoxEntry]]  # keyed by str(page_num), e.g. "0", "1"
    detected_lang: str  # BCP-47 / ISO 639-1 code, e.g. "en", "hi"; "unknown" if undetectable
    native_text_layer: dict[str, str] | None = None  # str(page_num) → text; None if all scanned
    metadata: JobMetadata


class P1ErrorPayload(BaseModel):
    """Payload returned when a job has permanently failed.

    P2 MUST NOT attempt routing; use error_code to classify and log.
    """

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    job_id: str
    status: Literal["failed"] = "failed"
    error_code: ErrorCode
    error_detail: str | None = None  # human-readable debug string; not for P2 logic
    metadata: JobMetadata


class P1PendingPayload(BaseModel):
    """Payload returned while the job is still in-flight.

    P2 should poll again; do not treat as ready.
    """

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    job_id: str
    status: Literal["queued", "processing", "preprocessed"]
    metadata: JobMetadata


__all__ = [
    "SCHEMA_VERSION",
    "BBoxEntry",
    "ErrorCode",
    "JobMetadata",
    "P1ErrorPayload",
    "P1OutputPayload",
    "P1PendingPayload",
    "PageImage",
]
