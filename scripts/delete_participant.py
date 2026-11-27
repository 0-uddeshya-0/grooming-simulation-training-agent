"""Researcher-side deletion on request: python scripts/delete_participant.py <participant-id>
Removes the participant's sessions, turns, snapshots, events, reviews, debriefs and consent record, then VACUUMs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import ROOT
from backend.store import Store

if len(sys.argv) != 2:
    sys.exit("usage: python scripts/delete_participant.py <participant-id>")
db = ROOT / "data" / "study.db"
if not db.exists():
    sys.exit("no database at data/study.db")
n = Store(db).delete_participant(sys.argv[1])
print(f"Deleted {n} session(s) for participant {sys.argv[1]}.")
