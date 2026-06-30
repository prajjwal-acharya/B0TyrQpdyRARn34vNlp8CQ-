import hashlib
import io
import uuid

import imagehash
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from minio import Minio
from minio.error import S3Error
from PIL import Image
from sqlalchemy.orm import Session

from shared.config import settings
from shared.db import get_db
from shared.models import Document

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

    return {"job_id": str(job_id), "deduplicated": False}
