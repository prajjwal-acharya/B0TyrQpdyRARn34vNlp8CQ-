# P1 → P2 Output Contract

**Schema version:** `1.0`
**Status:** Locked
**Owner:** P1 (Ingestion)
**Consumer:** P2 (Router)

This document is the **seam** between the ingestion pipeline (P1) and the routing service (P2).
P2 must build against this contract exclusively — no P1 internals should leak across it.

---

## Endpoint

```
GET /jobs/{job_id}
Host: ingestion-api:8000
```

### Path parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id`  | UUID string | The `job_id` returned by `POST /upload` |

---

## Response matrix

| HTTP status | Condition | Body schema |
|-------------|-----------|-------------|
| `200` | `status == "ready_for_routing"` | `P1OutputPayload` |
| `200` | `status == "failed"` | `P1ErrorPayload` |
| `202` | Job still in-flight | `P1PendingPayload` |
| `404` | Unknown `job_id` | `{"detail": "..."}` |

**P2 flow:**
1. Poll `GET /jobs/{job_id}` after a back-off interval.
2. On `202`: wait and retry.
3. On `200 + status == "ready_for_routing"`: proceed to routing.
4. On `200 + status == "failed"`: log the `error_code`, do not route.
5. On `404`: treat as a hard error.

---

## Schemas

All schemas share `schema_version: "1.0"`. P2 should reject payloads with unknown
schema versions to protect itself from future breaking changes.

### `P1OutputPayload`

Returned when `status == "ready_for_routing"`. All fields are guaranteed present.

```json
{
  "schema_version": "1.0",
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "ready_for_routing",
  "page_images": [
    {
      "page_num": 0,
      "minio_key": "processed/3fa85f64-5717-4562-b3fc-2c963f66afa6/page_0.png"
    }
  ],
  "bbox_data": {
    "0": [
      {
        "text": "Passport No: A1234567",
        "bbox": [[10,20],[200,20],[200,40],[10,40]],
        "confidence": 0.98,
        "source": "paddleocr"
      }
    ]
  },
  "detected_lang": "en",
  "native_text_layer": null,
  "metadata": {
    "filename": "passport.pdf",
    "mime_type": "application/pdf",
    "page_count": 1,
    "file_hash": "e3b0c44298fc1c149afb...",
    "created_at": "2026-06-30T10:00:00Z",
    "updated_at": "2026-06-30T10:00:05Z"
  }
}
```

#### Field reference

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | `"1.0"` literal | Bump on breaking changes |
| `job_id` | string (UUID) | Matches the upload `job_id` |
| `status` | `"ready_for_routing"` | Always this value in a 200 success |
| `page_images` | `PageImage[]` | One entry per page, 0-indexed |
| `page_images[].page_num` | int ≥ 0 | Page index |
| `page_images[].minio_key` | string | MinIO object key in the `processed` bucket |
| `bbox_data` | `dict[str, BBoxEntry[]]` | Key is `str(page_num)` |
| `bbox_data[n][].text` | string | OCR or native text for this region |
| `bbox_data[n][].bbox` | `float[4][2]` or `null` | Quad bbox; `null` for native-text pages |
| `bbox_data[n][].confidence` | float 0–1 | OCR confidence; `1.0` for native text |
| `bbox_data[n][].source` | `"paddleocr"` or `"native"` | Origin of the text |
| `detected_lang` | string | BCP-47/ISO 639-1 (e.g. `"en"`, `"hi"`); `"unknown"` if undetectable |
| `native_text_layer` | `dict[str, str]` or `null` | Page text for digital PDF pages; `null` if all scanned |
| `metadata.filename` | string | Original uploaded filename |
| `metadata.mime_type` | string or `null` | MIME type detected at upload |
| `metadata.page_count` | int ≥ 1 | Total pages processed |
| `metadata.file_hash` | string | SHA-256 or perceptual hash of the raw file |
| `metadata.created_at` | ISO 8601 datetime | Upload timestamp (UTC) |
| `metadata.updated_at` | ISO 8601 datetime | Last pipeline update (UTC) |

---

### `P1ErrorPayload`

Returned when `status == "failed"`. P2 **must not** route this document.

```json
{
  "schema_version": "1.0",
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "failed",
  "error_code": "ocr_failure",
  "error_detail": "PaddleOCR crashed on page 2 after 3 retries",
  "metadata": { "...": "same as above" }
}
```

#### Error codes

| `error_code` | Trigger condition |
|--------------|-------------------|
| `corrupt_file` | File is unreadable, truncated, or structurally invalid |
| `unsupported_format` | MIME type or file extension not supported by the pipeline |
| `ocr_failure` | PaddleOCR crashed or produced no output after max retries |
| `timeout` | A pipeline task exceeded its retry budget |
| `unknown` | Unclassified failure; check `error_detail` for the raw exception |

> `error_detail` is a human-readable debug string for logging only.
> P2 logic must branch on `error_code`, never on `error_detail`.

---

### `P1PendingPayload`

Returned (HTTP 202) when the job has not yet finished processing.

```json
{
  "schema_version": "1.0",
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "processing",
  "metadata": { "...": "same as above" }
}
```

`status` will be one of: `queued`, `processing`, `preprocessed`.

---

## Pydantic source of truth

The canonical schema is defined in [`shared/contracts/__init__.py`](../shared/contracts/__init__.py).
This document is derived from that file; if they diverge, the Python source wins.

---

## Versioning policy

| Change type | Action |
|-------------|--------|
| Add optional field | Bump minor in changelog only; schema_version stays `"1.0"` |
| Remove or rename field | Bump `schema_version` to `"2.0"`, run both versions in parallel during migration |
| Add new `error_code` value | Treat as non-breaking; P2 should handle unknown codes via `UNKNOWN` fallback |

---

## Accessing page images

Page images are stored in the MinIO `processed` bucket. To fetch a page image:

```python
client.get_object("processed", f"{job_id}/page_{page_num}.png")
```

Or use a presigned URL (once the presigned-URL endpoint is available in a future P1 release).
