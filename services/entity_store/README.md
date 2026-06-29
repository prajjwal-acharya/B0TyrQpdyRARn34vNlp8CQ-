# Service: Entity Store (Phase 10)

Persists validated entities to PostgreSQL and stores embeddings in pgvector for
semantic deduplication and retrieval.

## Responsibilities

- Write the final, validated extraction result to the `entities` table as JSONB
- Generate a document embedding via Gemini Embeddings API
- Store the embedding in pgvector for cosine similarity search
- Deduplicate against existing entities before writing
- Update the `documents` table status to `completed`

## Key Tech

- PostgreSQL + pgvector (storage + vector indexing)
- SQLAlchemy (ORM)
- Gemini Embeddings API (embedding generation)

## Data Model

See `infrastructure/postgres/init.sql` for the full schema.

Key tables:
- `entities` — validated entity JSONB + embedding vector
- `documents` — document status tracking
- `extracted_fields` — per-field extraction audit trail
