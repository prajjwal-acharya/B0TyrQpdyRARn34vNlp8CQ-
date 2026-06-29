# Adaptive AI Document Intelligence Platform

An end-to-end AI platform for extracting, validating, and storing structured information from
financial and identity documents — passports, ITR filings, bank statements, GST certificates,
property deeds, and salary slips.

## Novel Differentiators

- **LangGraph as AI-native orchestration** — the graph IS the architecture; every phase is a node or subgraph
- **RAG before extraction** — dynamic few-shot examples from past successful extractions prime each prompt
- **Computed multi-signal confidence engine** — confidence is not LLM self-reported; it is computed from OCR quality, schema compliance, cross-field consistency, retrieval similarity, and external verification signals
- **Field-level HITL via `LangGraph interrupt()`** — only low-confidence fields are sent for human review; the graph resumes automatically after correction
- **Continuous learning without retraining** — the system improves by updating prompts and the RAG retrieval index from accepted corrections (no model fine-tuning required)

## 12-Phase Architecture

| Phase | What it does | Key tech |
|-------|-------------|----------|
| 1 | Document ingestion & queuing | FastAPI, Celery, MinIO, Redis |
| 2 | Document type routing | LangGraph routing node, Groq/Llama3 |
| 3 | Schema registry lookup | YAML schemas, Pydantic v2 |
| 4 | Preprocessing & OCR | PyMuPDF, OpenCV, PaddleOCR, imagehash |
| 5 | RAG-primed extraction | LangGraph subgraphs, Gemini 1.5 Flash, ChromaDB |
| 6 | Confidence scoring | Multi-signal engine (OCR + schema + cross-field + retrieval + verification) |
| 7 | External validation | httpx, third-party APIs, Pydantic v2 |
| 8 | HITL review | LangGraph `interrupt()`, Label Studio |
| 9 | Continuous learning | Nightly Celery beat job, prompt + RAG updates |
| 10 | Entity storage | PostgreSQL + pgvector, SQLAlchemy |
| 11 | Query API | FastAPI, semantic search |
| 12 | Observability | LangSmith, Prometheus, Grafana, Loki, Fluent Bit |

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd adaptive-doc-intelligence
make setup          # copies .env.example to .env; fill in API keys

# 2. Start all services
make up

# 3. Verify (all containers should be healthy)
docker compose ps
```

## Team Setup

- **macOS** → [docs/setup-macos.md](docs/setup-macos.md)
- **Windows** → [docs/setup-windows.md](docs/setup-windows.md)

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| Ingestion API | http://localhost:8000 | Document upload & job submission |
| Flower | http://localhost:5555 | Celery task monitoring |
| MinIO Console | http://localhost:9001 | Object storage browser |
| Label Studio | http://localhost:8080 | HITL review interface |
| Prometheus | http://localhost:9090 | Metrics |
| Grafana | http://localhost:3000 | Dashboards (admin/admin) |
| Loki | http://localhost:3100 | Log aggregation |
| ChromaDB | http://localhost:8001 | Vector store HTTP API |

## Environment Variables

See [.env.example](.env.example) for the full list with inline comments.
Copy to `.env` and fill in your API keys before running `make up`.

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (extraction + embeddings) |
| `GROQ_API_KEY` | Groq API key (Llama3 routing) |
| `LANGCHAIN_API_KEY` | LangSmith API key (tracing) |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO credentials |
| `LABEL_STUDIO_TOKEN` | Label Studio API token |

## Contributing

1. Fork the repo and create a feature branch
2. Run `make lint` before pushing — CI enforces ruff + mypy
3. Add tests under `tests/unit/` or `tests/integration/`
4. Open a PR against `main`
