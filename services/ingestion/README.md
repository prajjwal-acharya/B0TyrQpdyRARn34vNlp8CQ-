# Service: Ingestion (Phase 1)

Accepts document uploads via FastAPI and queues them for async processing via Celery.

## Responsibilities

- Receive PDF/image uploads via `POST /documents/upload`
- Store raw files in MinIO (object storage)
- Create a `documents` record in PostgreSQL with status `pending`
- Enqueue a Celery task for the full processing pipeline
- Expose job status via `GET /documents/{id}/status`

## Key Tech

- FastAPI + Uvicorn
- Celery (task queue)
- Redis (broker + result backend)
- MinIO (raw document storage)
- PostgreSQL (metadata)

## Directory Layout

```
ingestion/
├── api/          # FastAPI app and routers
├── pipeline/     # Celery app definition and task graph
├── workers/      # Celery worker entry point
└── Dockerfile
```

## Running Locally

```bash
# Via Docker Compose (recommended)
make up

# API is available at http://localhost:8000
# Flower (task monitoring) at http://localhost:5555
```
