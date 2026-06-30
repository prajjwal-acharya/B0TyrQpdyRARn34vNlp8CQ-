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
│   ├── gst/
│   └── property_deed/
├── nodes/            # Reusable LangGraph nodes (OCR, RAG retrieval, LLM call, etc.)
├── chains/           # LCEL chains (prompt assembly, output parsing)
└── Dockerfile
```

Each `graphs/<doc_type>/graph.py` is currently a Phase 2B placeholder: a
single-node subgraph that just records it was entered, so the Phase 2
conditional dispatch (`services/router/router/graph.py`) can be proven
correct in LangGraph Studio. Real per-field extraction lands in Phase 5.
