SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS run_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL,
  command TEXT NOT NULL,
  key TEXT NOT NULL,
  row_index INTEGER NOT NULL DEFAULT 0,
  value_json TEXT,
  units TEXT,
  artifact_path TEXT,
  status TEXT NOT NULL,
  timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_measurements_lookup
  ON measurements(domain, command, key);

CREATE TABLE IF NOT EXISTS verifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL,
  command TEXT NOT NULL,
  key TEXT NOT NULL,
  expected_json TEXT,
  actual_json TEXT,
  tolerance_json TEXT,
  compare_op TEXT,
  status TEXT NOT NULL,
  optional INTEGER NOT NULL DEFAULT 0,
  message TEXT,
  step_name TEXT,
  timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  level TEXT NOT NULL,
  source TEXT NOT NULL,
  message TEXT NOT NULL,
  timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  path TEXT NOT NULL,
  description TEXT,
  timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL,
  command TEXT NOT NULL,
  key TEXT NOT NULL DEFAULT '',
  result_json TEXT,
  status TEXT NOT NULL,
  optional INTEGER NOT NULL DEFAULT 0,
  message TEXT,
  timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_commands_lookup
  ON commands(domain, command, key);
"""
