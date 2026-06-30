"""Unit tests for POST /upload — new file storage and repeat-upload dedup."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.ingestion.api.main import _RAW_BUCKET, _compute_file_hash, app
from shared.db import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(existing_doc=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing_doc
    return db


def _minio_mock(bucket_exists: bool = True):
    m = MagicMock()
    m.bucket_exists.return_value = bucket_exists
    return m


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# _compute_file_hash unit tests
# ---------------------------------------------------------------------------

def test_compute_file_hash_non_image_is_sha256():
    data = b"hello world"
    import hashlib
    expected = hashlib.sha256(data).hexdigest()
    assert _compute_file_hash(data, "application/pdf") == expected


def test_compute_file_hash_invalid_image_falls_back_to_sha256():
    data = b"not-an-image"
    import hashlib
    expected = hashlib.sha256(data).hexdigest()
    assert _compute_file_hash(data, "image/png") == expected


def test_compute_file_hash_image_uses_phash():
    from PIL import Image
    import io
    img = Image.new("RGB", (64, 64), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    h = _compute_file_hash(data, "image/png")
    # imagehash.phash produces 16 hex chars; sha256 produces 64 — check which we got
    assert len(h) == 16, "Image file should produce a 16-char imagehash phash"


# ---------------------------------------------------------------------------
# POST /upload — new file
# ---------------------------------------------------------------------------

@patch("services.ingestion.api.main._get_minio")
def test_upload_new_file_returns_job_id(mock_minio_factory, client):
    mock_minio_factory.return_value = _minio_mock()
    app.dependency_overrides[get_db] = lambda: _make_db(existing_doc=None)

    try:
        resp = client.post(
            "/upload",
            files={"file": ("report.pdf", b"PDF content bytes", "application/pdf")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "job_id" in body
        uuid.UUID(body["job_id"])  # must be a valid UUID
        assert body["deduplicated"] is False
    finally:
        app.dependency_overrides.clear()


@patch("services.ingestion.api.main._get_minio")
def test_upload_new_file_creates_minio_object(mock_minio_factory, client):
    mock_minio = _minio_mock()
    mock_minio_factory.return_value = mock_minio
    app.dependency_overrides[get_db] = lambda: _make_db(existing_doc=None)

    try:
        client.post(
            "/upload",
            files={"file": ("doc.txt", b"some content", "text/plain")},
        )
        mock_minio.put_object.assert_called_once()
        call_args = mock_minio.put_object.call_args
        assert call_args.args[0] == _RAW_BUCKET
    finally:
        app.dependency_overrides.clear()


@patch("services.ingestion.api.main._get_minio")
def test_upload_new_file_stores_minio_key_as_raw_prefix(mock_minio_factory, client):
    mock_minio = _minio_mock()
    mock_minio_factory.return_value = mock_minio
    captured_docs = []

    def fake_db():
        db = _make_db(existing_doc=None)
        db.add.side_effect = captured_docs.append
        return db

    app.dependency_overrides[get_db] = fake_db

    try:
        client.post(
            "/upload",
            files={"file": ("invoice.pdf", b"invoice data", "application/pdf")},
        )
        assert len(captured_docs) == 1
        assert captured_docs[0].minio_key.startswith(f"{_RAW_BUCKET}/")
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /upload — dedup (repeat-upload test)
# ---------------------------------------------------------------------------

@patch("services.ingestion.api.main._get_minio")
def test_repeat_upload_returns_existing_job_id(mock_minio_factory, client):
    """Uploading the same file twice must return the original job_id."""
    original_id = uuid.uuid4()
    existing = MagicMock()
    existing.id = original_id

    app.dependency_overrides[get_db] = lambda: _make_db(existing_doc=existing)

    try:
        resp = client.post(
            "/upload",
            files={"file": ("dup.pdf", b"duplicate content", "application/pdf")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["job_id"] == str(original_id)
        assert body["deduplicated"] is True
    finally:
        app.dependency_overrides.clear()


@patch("services.ingestion.api.main._get_minio")
def test_repeat_upload_skips_minio(mock_minio_factory, client):
    """Duplicate file must not touch MinIO."""
    existing = MagicMock()
    existing.id = uuid.uuid4()

    app.dependency_overrides[get_db] = lambda: _make_db(existing_doc=existing)

    try:
        client.post(
            "/upload",
            files={"file": ("dup.pdf", b"duplicate content", "application/pdf")},
        )
        mock_minio_factory.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@patch("services.ingestion.api.main._get_minio")
def test_repeat_upload_skips_db_write(mock_minio_factory, client):
    """Duplicate file must not insert a new row."""
    mock_minio_factory.return_value = _minio_mock()
    existing = MagicMock()
    existing.id = uuid.uuid4()
    mock_db = _make_db(existing_doc=existing)

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        client.post(
            "/upload",
            files={"file": ("dup.pdf", b"duplicate content", "application/pdf")},
        )
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
