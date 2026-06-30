# Service: Router (Phase 2)

A LangGraph routing node that classifies an incoming document into one of the supported
document types: `passport`, `itr`, `bank_statement`, `form_16`, `salary_slip`, `gst`,
or `property_deed`.

## Responsibilities

- Receive preprocessed document text / metadata from Phase 1
- Use Groq/Llama3 (escalating to Gemini Flash when unsure) to classify the doc type
- Write the detected `doc_type` back to the graph state
- Use a LangGraph conditional edge, keyed on `doc_type`, to dispatch into the
  matching doc-type extraction subgraph (Phase 5, currently stubbed in
  `services/extraction/graphs`)
- Explicitly route unknown or low-confidence classifications to a
  `fallback_review` branch instead of silently defaulting to a doc type

## Key Tech

- LangGraph (routing node + conditional edge)
- Groq API (Llama3 model) + Gemini Flash (multimodal fallback)
- LangSmith (tracing)

## Directory Layout

```
router/
├── router/
│   ├── node.py       # classify_document — Groq fast-path, Gemini fallback
│   ├── fallback.py   # explicit fallback_review branch for unknown/low-confidence doc_type
│   ├── graph.py       # conditional dispatch: classify -> doc-type subgraph | fallback
│   ├── schemas.py
│   └── main.py
└── Dockerfile
```

`LOW_CONFIDENCE_THRESHOLD` (env var, default `0.5`) controls the floor on the
*final* classification confidence (after any Groq → Gemini escalation) below
which a document is routed to `fallback_review` rather than a doc-type
subgraph.
