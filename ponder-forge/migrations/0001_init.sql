CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  parent_session_id TEXT,
  user_goal TEXT NOT NULL,
  profile TEXT NOT NULL,
  status TEXT NOT NULL,
  budget_json TEXT NOT NULL DEFAULT '{}',
  config_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  final_report_md TEXT
);

CREATE TABLE IF NOT EXISTS workflow_nodes (
  node_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  profile TEXT NOT NULL,
  node_type TEXT NOT NULL,
  role TEXT NOT NULL,
  status TEXT NOT NULL,
  input_json TEXT NOT NULL DEFAULT '{}',
  output_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_tasks (
  task_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  node_id TEXT,
  parent_task_id TEXT,
  hermes_child_session_id TEXT,
  hermes_subagent_id TEXT,
  role TEXT NOT NULL,
  goal TEXT NOT NULL,
  context TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  delegation_id TEXT,
  started_at TEXT,
  finished_at TEXT,
  error TEXT,
  raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS reports (
  report_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  task_id TEXT,
  role TEXT NOT NULL,
  title TEXT,
  summary TEXT NOT NULL,
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'submitted',
  created_at TEXT NOT NULL,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assertions (
  assertion_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  report_id TEXT,
  profile TEXT NOT NULL,
  assertion_type TEXT NOT NULL,
  text TEXT NOT NULL,
  importance REAL NOT NULL DEFAULT 0.5,
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'unverified',
  subject TEXT,
  predicate TEXT,
  object TEXT,
  supersedes_assertion_id TEXT,
  created_at TEXT NOT NULL,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_items (
  evidence_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  report_id TEXT,
  assertion_id TEXT,
  evidence_type TEXT NOT NULL,
  source_ref TEXT,
  title TEXT,
  quote_or_observation TEXT,
  locator TEXT,
  source_date TEXT,
  retrieved_at TEXT,
  reliability REAL NOT NULL DEFAULT 0.5,
  relevance REAL NOT NULL DEFAULT 0.5,
  directness REAL NOT NULL DEFAULT 0.5,
  freshness REAL NOT NULL DEFAULT 0.5,
  counterevidence INTEGER NOT NULL DEFAULT 0,
  artifact_path TEXT,
  command TEXT,
  exit_code INTEGER,
  metric_json TEXT NOT NULL DEFAULT '{}',
  quote_hash TEXT,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  report_id TEXT,
  artifact_type TEXT NOT NULL,
  path TEXT,
  summary TEXT,
  created_at TEXT NOT NULL,
  raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS graph_edges (
  edge_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  src_type TEXT NOT NULL,
  src_id TEXT NOT NULL,
  dst_type TEXT NOT NULL,
  dst_id TEXT NOT NULL,
  edge_type TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verification_verdicts (
  verdict_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  profile TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  reviewer_role TEXT NOT NULL,
  reviewer_task_id TEXT,
  verifier_mode TEXT NOT NULL,
  independent_from_task_id TEXT,
  verdict TEXT NOT NULL,
  confidence REAL,
  rationale TEXT,
  required_actions_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS final_statements (
  statement_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  section TEXT NOT NULL,
  text TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS statement_assertion_links (
  statement_id TEXT NOT NULL,
  assertion_id TEXT NOT NULL,
  relation TEXT NOT NULL,
  PRIMARY KEY(statement_id, assertion_id)
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT,
  task_id TEXT,
  session_id TEXT,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL DEFAULT 'system',
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
