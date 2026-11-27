-- Local SQLite, pseudonymous participant IDs only. journal_mode=DELETE (no WAL files) so deletion is complete.
CREATE TABLE IF NOT EXISTS participants (
  pid TEXT PRIMARY KEY,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS consents (
  pid TEXT NOT NULL REFERENCES participants(pid),
  consent_version TEXT NOT NULL,
  age_confirmed INTEGER NOT NULL,
  consented_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  sid TEXT PRIMARY KEY,
  pid TEXT NOT NULL REFERENCES participants(pid),
  persona_id TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  started_at REAL NOT NULL,
  ended_at REAL,
  end_reason TEXT          -- stop | timeout | distress | user_minor | limit_pushes | filter_exhausted
);
CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sid TEXT NOT NULL REFERENCES sessions(sid),
  idx INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user','attacker')),
  text TEXT NOT NULL,
  ts REAL NOT NULL,
  primary_strategy INTEGER,    -- 0..5 index into STRATEGIES (attacker turns)
  secondary_strategy INTEGER
);
CREATE TABLE IF NOT EXISTS state_snapshots (
  sid TEXT NOT NULL REFERENCES sessions(sid),
  turn INTEGER NOT NULL,
  stage INTEGER NOT NULL,
  offender_type REAL NOT NULL,
  register REAL NOT NULL,
  receptiveness REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  sid TEXT NOT NULL REFERENCES sessions(sid),
  ts REAL NOT NULL,
  kind TEXT NOT NULL,     -- filter_hit | antirepeat_retry | limit_push | distress | ...
  detail TEXT
);
CREATE TABLE IF NOT EXISTS debriefs (
  sid TEXT PRIMARY KEY REFERENCES sessions(sid),
  created_at REAL NOT NULL,
  content_json TEXT NOT NULL
);
