# Service: Validation (Phase 7)

Validates extracted fields against external APIs and Pydantic v2 schemas.

## Responsibilities

- Run validation rules defined in the doc-type YAML schema (e.g., PAN format, IFSC format)
- Call external APIs for field-level verification (e.g., GSTIN lookup, IFSC lookup)
- Validate the full extraction result against the Pydantic v2 model
- Return a `ValidationResult` with per-rule pass/fail and an overall validity flag
- Write audit records to the `validation_audit` table

## Key Tech

- httpx (async HTTP for external API calls)
- Pydantic v2 (schema validation)
- PostgreSQL (audit logging)
