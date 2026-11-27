"""Researcher-side session log viewer. Separate app/port (default 8001), localhost only, token-protected.
Not mounted by the participant app; the UI file lives outside frontend/ so participants cannot fetch it."""
import csv
import io
import os
import secrets
import time
from pathlib import Path
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from . import constants as C
from .config import ROOT, load_personas
from .director import exposure
from .store import Store


class ReviewReq(BaseModel):
    sid: str
    idx: int
    agree: bool


def create_researcher_app(db_path=None, token: str | None = None) -> FastAPI:
    token = token or os.environ.get("RESEARCHER_TOKEN") or secrets.token_urlsafe(16)
    store = Store(db_path or ROOT / "data" / "study.db")
    personas = load_personas()
    app = FastAPI(title="Researcher log viewer", docs_url=None, redoc_url=None)
    app.state.token = token

    def auth(rt: str | None = Cookie(default=None), x_researcher_token: str | None = Header(default=None)):
        if not (secrets.compare_digest(rt or "", token) or secrets.compare_digest(x_researcher_token or "", token)):
            raise HTTPException(401, "researcher token required")

    def pname(pid_):
        return personas[pid_]["name"] if pid_ in personas else pid_

    def strat(i):
        return C.STRATEGIES[i] if i is not None else None

    @app.get("/")
    def index(token: str | None = Query(default=None), rt: str | None = Cookie(default=None)):
        if token is not None and secrets.compare_digest(token, app.state.token):
            r = RedirectResponse("/")
            r.set_cookie("rt", token, httponly=True, samesite="strict")
            return r
        if not secrets.compare_digest(rt or "", app.state.token):
            return HTMLResponse("<h3>Researcher viewer</h3><p>Open the URL printed by scripts/researcher (it contains the token).</p>", 401)
        return HTMLResponse((Path(__file__).parent / "researcher_ui" / "index.html").read_text(encoding="utf-8"))

    @app.get("/api/r/sessions", dependencies=[Depends(auth)])
    def sessions():
        out = []
        for s in store.all_sessions():
            dur = (s["ended_at"] - s["started_at"]) if s["ended_at"] else None
            out.append({**s, "persona": pname(s["persona_id"]), "duration_s": round(dur) if dur else None,
                        "tag_accuracy": (round(100 * s["n_agree"] / s["n_reviewed"]) if s["n_reviewed"] else None)})
        return out

    @app.get("/api/r/session/{sid}", dependencies=[Depends(auth)])
    def session(sid: str):
        s = store.session(sid)
        if not s:
            raise HTTPException(404)
        turns, rev = store.turns(sid), store.reviews(sid)
        for t in turns:
            t["primary"], t["secondary"] = strat(t["primary_strategy"]), strat(t["secondary_strategy"])
            t["review"] = rev.get(t["idx"])
        hist = [(t["primary_strategy"], t["secondary_strategy"]) for t in turns if t["role"] == "attacker"]
        return {"session": {**dict(s), "persona": pname(s["persona_id"])}, "turns": turns, "events": store.events(sid),
                "snapshots": store.snapshots(sid), "exposure": exposure(hist),
                "reviewed": len(rev), "agree": sum(rev.values())}

    @app.post("/api/r/review", dependencies=[Depends(auth)])
    def review(r: ReviewReq):
        if not store.session(r.sid):
            raise HTTPException(404)
        store.set_review(r.sid, r.idx, r.agree, time.time())
        rev = store.reviews(r.sid)
        return {"reviewed": len(rev), "agree": sum(rev.values())}

    @app.get("/api/r/export.csv", dependencies=[Depends(auth)])
    def export_csv():
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(["participant", "session", "persona", "turn_idx", "role", "time", "primary_strategy", "secondary_strategy", "tag_review", "text"])
        for s in reversed(store.all_sessions()):
            rev = store.reviews(s["sid"])
            for t in store.turns(s["sid"]):
                w.writerow([s["pid"], s["sid"], s["persona_id"], t["idx"], t["role"], t["ts"], strat(t["primary_strategy"]) or "",
                            strat(t["secondary_strategy"]) or "", rev.get(t["idx"], ""), t["text"]])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=study_turns.csv"})

    @app.delete("/api/r/participant/{pid}", dependencies=[Depends(auth)])
    def delete(pid: str):
        return {"deleted_sessions": store.delete_participant(pid)}

    return app


def main():
    import threading, webbrowser, uvicorn
    app = create_researcher_app()
    port = int(os.environ.get("RESEARCHER_PORT", "8001"))
    url = f"http://127.0.0.1:{port}/?token={app.state.token}"
    print("\nResearcher viewer (keep private):\n  " + url + "\n")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
