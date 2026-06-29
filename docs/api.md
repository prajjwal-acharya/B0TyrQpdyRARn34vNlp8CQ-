# API Reference

> This document is a placeholder. Full API documentation will be generated from FastAPI's
> automatic OpenAPI spec once the ingestion and query services are implemented.

## Ingestion API — `http://localhost:8000`

Interactive docs available at: http://localhost:8000/docs

### Planned Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/documents/upload` | Upload a document for processing |
| `GET` | `/documents/{id}/status` | Poll processing status |
| `GET` | `/documents/{id}/result` | Retrieve extraction result |
| `POST` | `/hitl/{task_id}/review` | Submit a HITL correction |

## Query API — `http://localhost:8000/query` (Phase 11)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/query/semantic` | Semantic search over extracted entities |
| `GET` | `/entities/{id}` | Retrieve a stored entity by ID |

## Authentication

> TODO: Define authentication scheme (API key / OAuth2) once Phase 11 is implemented.
