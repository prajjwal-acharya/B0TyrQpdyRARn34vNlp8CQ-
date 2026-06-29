# Service: Router (Phase 2)

A LangGraph routing node that classifies an incoming document into one of the supported
document types: `passport`, `itr`, `bank_statement`, `form_16`, `salary_slip`, `gst`,
or `property_deed`.

## Responsibilities

- Receive preprocessed document text / metadata from Phase 1
- Use Groq/Llama3 via a LangGraph conditional edge to classify the doc type
- Write the detected `doc_type` back to the graph state
- Route the graph to the appropriate doc-type-specific extraction subgraph (Phase 5)

## Key Tech

- LangGraph (routing node + conditional edge)
- Groq API (Llama3 model)
- LangSmith (tracing)

## Directory Layout

```
router/
├── router/      # routing node implementation (to be created)
└── Dockerfile
```
