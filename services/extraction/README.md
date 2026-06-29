# Service: Extraction (Phases 4 + 5)

Handles document preprocessing (Phase 4) and RAG-primed LLM extraction (Phase 5).

## Phase 4 — Preprocessing

- PDF text + layout extraction via PyMuPDF
- Image quality assessment via OpenCV
- OCR with bounding boxes via PaddleOCR
- Duplicate detection via imagehash
- Language detection via langdetect

## Phase 5 — Extraction

- Retrieves few-shot examples from ChromaDB (RAG) based on the current document's embedding
- Dynamically assembles an extraction prompt using the doc-type YAML schema + few-shot examples
- Calls Gemini 1.5 Flash via a LangGraph subgraph specific to each document type
- Returns a structured JSON extraction result with per-field confidence signals

## Directory Layout

```
extraction/
├── graphs/           # LangGraph subgraphs, one per doc type
│   ├── passport/
│   ├── itr/
│   ├── bank_statement/
│   ├── form_16/
│   ├── salary_slip/
│   └── property_deed/
├── nodes/            # Reusable LangGraph nodes (OCR, RAG retrieval, LLM call, etc.)
├── chains/           # LCEL chains (prompt assembly, output parsing)
└── Dockerfile
```
