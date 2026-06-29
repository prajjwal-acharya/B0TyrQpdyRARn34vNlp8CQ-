# Architecture Overview

## 12-Phase Pipeline

The platform processes documents through a directed graph of phases orchestrated by LangGraph.
Each phase is a LangGraph node or subgraph. State flows between phases via a typed `GraphState`
Pydantic model.

```
[Upload] → [Route] → [Schema Lookup] → [Preprocess + OCR]
         ↓
   [RAG Retrieval] → [LLM Extraction] → [Confidence Score]
         ↓
   [Validation] → [HITL? interrupt()] → [Entity Storage]
         ↓
   [Learning Update] → [Query API] → [Observability]
```

### Phase Descriptions

| Phase | Service | Description |
|-------|---------|-------------|
| 1 — Ingestion | `services/ingestion` | FastAPI endpoint accepts PDF/image uploads. Files are stored in MinIO. A Celery task is enqueued for async processing. |
| 2 — Routing | `services/router` | A LangGraph routing node uses Groq/Llama3 to classify the document type (passport, ITR, etc.). |
| 3 — Schema Lookup | `shared/schemas` | The YAML schema for the detected doc type is loaded. It specifies fields, validation rules, confidence thresholds, and the prompt template ref. |
| 4 — Preprocessing | `services/extraction` | PyMuPDF extracts text + layout. OpenCV handles image quality. PaddleOCR provides bounding boxes. imagehash detects duplicates. langdetect identifies language. |
| 5 — Extraction | `services/extraction/graphs` | A doc-type-specific LangGraph subgraph retrieves few-shot examples from ChromaDB (RAG), then calls Gemini 1.5 Flash with a dynamically assembled prompt. |
| 6 — Confidence | `services/confidence` | Five signals are combined: OCR quality score, schema compliance rate, cross-field consistency checks, RAG retrieval similarity, and external verification results. |
| 7 — Validation | `services/validation` | External API calls verify key fields (e.g., PAN format, IFSC codes). Pydantic v2 validates the full extracted record against the schema. |
| 8 — HITL | `services/hitl` | Fields below the confidence threshold trigger `LangGraph interrupt()`. Tasks are pushed to Label Studio. The graph resumes after a human correction is received. |
| 9 — Learning | `services/learning` | A nightly Celery beat job updates the prompt templates and adds accepted extractions to the ChromaDB RAG index. No model retraining occurs. |
| 10 — Entity Store | `services/entity_store` | Validated entities are written to PostgreSQL. Embeddings are stored in pgvector for semantic dedup and retrieval. |
| 11 — Query API | `services/query` | A FastAPI service exposes REST + semantic search endpoints over the entity store. |
| 12 — Observability | Infrastructure | LangSmith traces every LLM call. Prometheus + Grafana provide system metrics. Loki + Fluent Bit aggregate logs. OpenTelemetry spans bridge services. |

## Diagram Placeholder

> TODO: Add a Mermaid or draw.io graph of the full LangGraph state machine here.
