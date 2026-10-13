CREATE TABLE documents (
    document_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(document_id)) > 0),
    owner_id TEXT NOT NULL CHECK (length(trim(owner_id)) > 0),
    filename TEXT NOT NULL CHECK (length(trim(filename)) > 0),
    source_checksum TEXT NOT NULL CHECK (
        length(source_checksum) = 64 AND source_checksum NOT GLOB '*[^0-9a-f]*'
    ),
    pipeline_version TEXT NOT NULL CHECK (length(trim(pipeline_version)) > 0),
    status TEXT NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
    num_pages INTEGER CHECK (num_pages IS NULL OR (typeof(num_pages) = 'integer' AND num_pages > 0)),
    num_chunks INTEGER CHECK (num_chunks IS NULL OR (typeof(num_chunks) = 'integer' AND num_chunks > 0)),
    failure_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (owner_id, source_checksum, pipeline_version),
    CHECK (
        (status = 'processing' AND num_pages IS NULL AND num_chunks IS NULL AND failure_code IS NULL)
        OR (status = 'ready' AND num_pages IS NOT NULL AND num_chunks IS NOT NULL AND failure_code IS NULL)
        OR (status = 'failed' AND num_pages IS NULL AND num_chunks IS NULL AND length(trim(failure_code)) > 0 AND failure_code IS NOT NULL)
    )
)
