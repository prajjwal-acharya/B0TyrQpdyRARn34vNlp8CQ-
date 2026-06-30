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
- Log every classification to the `routing_decisions` Postgres audit table
  (job_id, doc_type, confidence, model_used, reasoning, timestamp) so any
  routing decision can be queried and explained after the fact

## Key Tech

- LangGraph (routing node + conditional edge)
- Groq API (Llama3 model) + Gemini Flash (multimodal fallback)
- LangSmith (tracing — every LLM call is tagged `router-node` plus the
  specific model used, so router traces are filterable from the rest of the
  pipeline)
- PostgreSQL (`routing_decisions` audit log table)

## Directory Layout

```
router/
├── router/
│   ├── node.py       # classify_document — Groq fast-path, Gemini fallback
│   ├── audit.py       # routing_decisions audit log — write + query by job_id
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

## Audit Log

Every classification (`classify_document`) writes a row to the
`routing_decisions` table via `audit.log_routing_decision` — `model_used`
records the specific model that produced the final decision (e.g.
`groq:llama3-8b-8192` or `gemini:gemini-1.5-flash`), so a low-confidence
Groq call that escalated to Gemini is fully traceable. Logging failures are
caught and logged, never raised — a broken audit write must not break
routing.

Query the rationale for any job via the ingestion API:

```
GET /routing-decisions/{job_id}
```

returns `{job_id, doc_type, confidence, model_used, reasoning, fallback_used, timestamp}`,
or `404` if no decision has been logged for that job yet.
