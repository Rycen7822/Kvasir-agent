CREATE TABLE artifacts_replacement (
    artifact_id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    schema_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    producer_agent TEXT NOT NULL,
    title TEXT,
    content_json TEXT NOT NULL,
    file_path TEXT,
    status TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);
INSERT INTO artifacts_replacement (
    artifact_id, room_id, schema_id, artifact_type, producer_agent, title,
    content_json, status, confidence, created_at, updated_at, metadata_json
)
SELECT artifact_id, room_id, schema_id, artifact_type, producer_agent, title,
    content_json, status, confidence, created_at, updated_at, metadata_json
FROM artifacts;
DROP TABLE artifacts;
ALTER TABLE artifacts_replacement RENAME TO artifacts;
CREATE INDEX idx_artifacts_room_type_status ON artifacts(room_id, artifact_type, status);
CREATE INDEX idx_artifacts_room_producer ON artifacts(room_id, producer_agent);
