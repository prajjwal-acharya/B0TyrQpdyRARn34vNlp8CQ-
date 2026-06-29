# Service: Continuous Learning (Phase 9)

Runs a nightly Celery Beat job that improves the system without retraining any model.

## Responsibilities

- Query the `corrections` table for accepted HITL corrections from the past 24 hours
- Add successful extraction+correction pairs to the ChromaDB RAG index as new few-shot examples
- Update prompt templates based on patterns in corrections (e.g., common OCR errors)
- Increment schema version in `schema_versions` if prompt templates change

## Key Design Choice

No model retraining. The system improves through:
1. **Retrieval improvement** — new examples in ChromaDB make future RAG retrieval more relevant
2. **Prompt improvement** — updated Jinja2 templates incorporate learned correction patterns

## Schedule

The Celery Beat scheduler runs this task daily at 02:00 UTC (configurable via environment).

## Key Tech

- Celery Beat (nightly scheduler)
- ChromaDB (RAG index update)
- PostgreSQL (read corrections, write schema versions)
