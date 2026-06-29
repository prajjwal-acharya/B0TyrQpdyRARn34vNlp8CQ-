-- Enable pgvector extension for semantic similarity search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- documents — raw document metadata
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename    TEXT NOT NULL,
    doc_type    TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    minio_key   TEXT,
    hash        TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- extracted_fields — per-field extraction results
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS extracted_fields (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    field_name   TEXT NOT NULL,
    raw_value    TEXT,
    parsed_value JSONB,
    confidence   NUMERIC(5, 4),
    is_corrected BOOLEAN NOT NULL DEFAULT FALSE,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- entities — validated, stored entities (one row per document)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entities (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    doc_type    TEXT NOT NULL,
    data        JSONB NOT NULL,
    embedding   vector(768),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- validation_audit — per-document validation run log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS validation_audit (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    rule_name   TEXT NOT NULL,
    passed      BOOLEAN NOT NULL,
    detail      TEXT,
    checked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- corrections — HITL corrections submitted by reviewers
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS corrections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    field_name      TEXT NOT NULL,
    original_value  TEXT,
    corrected_value TEXT NOT NULL,
    reviewer        TEXT,
    corrected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- schema_versions — registry of YAML schema versions per doc type
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_versions (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_type   TEXT NOT NULL,
    version    TEXT NOT NULL,
    yaml_path  TEXT NOT NULL,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_type, version)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_documents_doc_type  ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_status    ON documents(status);
CREATE INDEX IF NOT EXISTS idx_extracted_fields_document ON extracted_fields(document_id);
CREATE INDEX IF NOT EXISTS idx_entities_doc_type   ON entities(doc_type);
CREATE INDEX IF NOT EXISTS idx_entities_embedding  ON entities USING ivfflat (embedding vector_cosine_ops);
