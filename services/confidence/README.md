# Service: Confidence Engine (Phase 6)

Computes a multi-signal confidence score for each extracted field. Confidence is not
self-reported by the LLM — it is computed from five independent signals.

## Signals

| Signal | Weight (default) | Description |
|--------|-----------------|-------------|
| OCR quality | 0.30 | Character-level confidence from PaddleOCR |
| Schema compliance | 0.25 | Ratio of fields matching expected type/pattern |
| Cross-field consistency | 0.20 | Logical constraints between fields (e.g., issue < expiry) |
| Retrieval similarity | 0.15 | Cosine similarity to top-k RAG examples |
| External verification | 0.10 | Result of external API validation checks |

Weights are configurable per doc type via the YAML schema files in `shared/schemas/`.

## Output

A `ConfidenceResult` object with:
- `overall_confidence: float` — weighted average across all signals
- `field_confidences: dict[str, float]` — per-field score
- `low_confidence_fields: list[str]` — fields below the doc-type threshold (trigger HITL)
