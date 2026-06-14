CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    room_id TEXT PRIMARY KEY,
    title TEXT,
    topic TEXT,
    protocol TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_created_at ON rooms(created_at);

CREATE TABLE IF NOT EXISTS participants (
    room_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT,
    display_name TEXT,
    status TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (room_id, agent_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);
CREATE INDEX IF NOT EXISTS idx_participants_room ON participants(room_id);
CREATE INDEX IF NOT EXISTS idx_participants_role ON participants(room_id, role);

CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    round_id TEXT,
    phase TEXT,
    agent_id TEXT NOT NULL,
    role TEXT,
    content TEXT NOT NULL,
    artifact_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);
CREATE INDEX IF NOT EXISTS idx_messages_room_round_phase ON messages(room_id, round_id, phase);
CREATE INDEX IF NOT EXISTS idx_messages_room_created ON messages(room_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_agent ON messages(room_id, agent_id);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    schema_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    producer_agent TEXT NOT NULL,
    title TEXT,
    content_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(room_id, artifact_type, content_hash),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);
CREATE INDEX IF NOT EXISTS idx_artifacts_room_type_status ON artifacts(room_id, artifact_type, status);
CREATE INDEX IF NOT EXISTS idx_artifacts_room_producer ON artifacts(room_id, producer_agent);
CREATE INDEX IF NOT EXISTS idx_artifacts_hash ON artifacts(content_hash);

CREATE TABLE IF NOT EXISTS artifact_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_artifact_id TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(room_id, source_artifact_id, relation, target_artifact_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    FOREIGN KEY (source_artifact_id) REFERENCES artifacts(artifact_id),
    FOREIGN KEY (target_artifact_id) REFERENCES artifacts(artifact_id)
);
CREATE INDEX IF NOT EXISTS idx_links_source ON artifact_links(room_id, source_artifact_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON artifact_links(room_id, target_artifact_id);
CREATE INDEX IF NOT EXISTS idx_links_relation ON artifact_links(room_id, relation);

CREATE TABLE IF NOT EXISTS gates (
    gate_id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    input_artifact_ids_json TEXT NOT NULL DEFAULT '[]',
    decision TEXT NOT NULL,
    score_json TEXT NOT NULL DEFAULT '{}',
    rationale TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);
CREATE INDEX IF NOT EXISTS idx_gates_room_type ON gates(room_id, gate_type);
CREATE INDEX IF NOT EXISTS idx_gates_room_decision ON gates(room_id, decision);

CREATE TABLE IF NOT EXISTS open_needs (
    need_id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    target_artifact_type TEXT NOT NULL,
    query TEXT NOT NULL,
    rationale TEXT NOT NULL,
    pressure_score REAL NOT NULL,
    status TEXT NOT NULL,
    claimed_by_agent TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);
CREATE INDEX IF NOT EXISTS idx_open_needs_room_status ON open_needs(room_id, status);
CREATE INDEX IF NOT EXISTS idx_open_needs_pressure ON open_needs(room_id, pressure_score);
