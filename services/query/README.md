# Service: Query API (Phase 11)

Exposes REST and semantic search endpoints over the validated entity store.

## Responsibilities

- `GET /entities/{id}` — retrieve a stored entity by ID
- `POST /query/semantic` — semantic search using pgvector cosine similarity
- `GET /entities?doc_type=passport&...` — filtered entity listing
- Support for pagination and field-level filtering

## Key Tech

- FastAPI + Uvicorn
- PostgreSQL + pgvector (vector similarity search)
- SQLAlchemy (query layer)
- Gemini Embeddings API (query embedding for semantic search)

## Example: Semantic Search

```json
POST /query/semantic
{
  "query": "Rahul Sharma passport Mumbai",
  "doc_type": "passport",
  "top_k": 5
}
```

Returns the top-5 most semantically similar entities from the store.
