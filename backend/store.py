import json
import sqlite3
import time
from pathlib import Path
from .config import ROOT


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript((ROOT / "docs" / "SCHEMA.sql").read_text())

    def q(self, sql, *a):
        cur = self.db.execute(sql, a)
        self.db.commit()
        return cur

    def add_participant(self, pid, consent_version, age_confirmed, now):
        self.q("INSERT OR IGNORE INTO participants VALUES (?,?)", pid, now)
        self.q("INSERT INTO consents VALUES (?,?,?,?)", pid, consent_version, int(age_confirmed), now)

    def add_session(self, sid, pid, persona_id, cfg_hash, now):
        self.q("INSERT INTO sessions (sid,pid,persona_id,config_hash,started_at) VALUES (?,?,?,?,?)",
               sid, pid, persona_id, cfg_hash, now)

    def end_session(self, sid, reason, now) -> bool:
        """Atomic: only the first caller ends the session."""
        cur = self.q("UPDATE sessions SET ended_at=?, end_reason=? WHERE sid=? AND ended_at IS NULL", now, reason, sid)
        return cur.rowcount == 1

    def session(self, sid):
        return self.q("SELECT * FROM sessions WHERE sid=?", sid).fetchone()

    def sessions_for(self, pid):
        return [dict(r) for r in self.q("SELECT * FROM sessions WHERE pid=? ORDER BY started_at", pid)]

    def open_sessions(self):
        return [dict(r) for r in self.q("SELECT sid, started_at FROM sessions WHERE ended_at IS NULL")]

    def add_turn(self, sid, role, text, now, primary=None, secondary=None):
        idx = self.q("SELECT COUNT(*) c FROM turns WHERE sid=?", sid).fetchone()["c"]
        self.q("INSERT INTO turns (sid,idx,role,text,ts,primary_strategy,secondary_strategy) VALUES (?,?,?,?,?,?,?)",
               sid, idx, role, text, now, primary, secondary)

    def turns(self, sid):
        return [dict(r) for r in self.q("SELECT * FROM turns WHERE sid=? ORDER BY idx", sid)]

    def snapshot(self, sid, s):
        self.q("INSERT INTO state_snapshots VALUES (?,?,?,?,?,?)", sid, s.turn, s.stage, s.offender_type, s.register, s.receptiveness)

    def snapshots(self, sid):
        return [dict(r) for r in self.q("SELECT * FROM state_snapshots WHERE sid=? ORDER BY turn", sid)]

    def event(self, sid, kind, detail="", now=None):
        self.q("INSERT INTO events VALUES (?,?,?,?)", sid, now or time.time(), kind, detail)

    def events(self, sid):
        return [dict(r) for r in self.q("SELECT * FROM events WHERE sid=? ORDER BY ts", sid)]

    def set_review(self, sid, idx, agree, now):
        self.q("INSERT OR REPLACE INTO tag_reviews VALUES (?,?,?,?)", sid, idx, int(agree), now)

    def reviews(self, sid):
        return {r["idx"]: r["agree"] for r in self.q("SELECT idx, agree FROM tag_reviews WHERE sid=?", sid)}

    def all_sessions(self):
        return [dict(r) for r in self.q("""SELECT s.*,
            (SELECT COUNT(*) FROM turns t WHERE t.sid=s.sid AND t.role='user') AS n_user,
            (SELECT COUNT(*) FROM turns t WHERE t.sid=s.sid AND t.role='attacker') AS n_attacker,
            (SELECT COUNT(*) FROM events e WHERE e.sid=s.sid AND e.kind='filter_hit') AS n_filter_hits,
            (SELECT COUNT(*) FROM tag_reviews r WHERE r.sid=s.sid) AS n_reviewed,
            (SELECT COALESCE(SUM(agree),0) FROM tag_reviews r WHERE r.sid=s.sid) AS n_agree
            FROM sessions s ORDER BY s.started_at DESC""")]

    def save_debrief(self, sid, content, now):
        self.q("INSERT OR REPLACE INTO debriefs VALUES (?,?,?)", sid, now, json.dumps(content))

    def delete_participant(self, pid):
        sids = [r["sid"] for r in self.q("SELECT sid FROM sessions WHERE pid=?", pid)]
        for sid in sids:
            for t in ("turns", "state_snapshots", "events", "debriefs", "tag_reviews"):
                self.q(f"DELETE FROM {t} WHERE sid=?", sid)
        self.q("DELETE FROM sessions WHERE pid=?", pid)
        self.q("DELETE FROM consents WHERE pid=?", pid)
        self.q("DELETE FROM participants WHERE pid=?", pid)
        self.db.execute("VACUUM")
        return len(sids)
