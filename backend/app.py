"""FastAPI app. Binds to localhost; static frontend; no outbound calls."""
import os
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .config import ROOT, HelplinesStale, load_app, load_helplines, load_personas
from .debrief import build_debrief
from .engine import Engine
from .llm import LlamaServer, MockLLM
from .store import Store


class StartReq(BaseModel):
    participant_id: str
    persona_id: str
    consent: bool
    age_confirmed: bool


class MsgReq(BaseModel):
    text: str


def create_app(cfg=None, llm=None, db_path=None, check_helplines=True) -> FastAPI:
    cfg = cfg or load_app()
    personas = load_personas()
    if check_helplines:
        load_helplines(max_age_days=cfg["limits"]["helplines_max_age_days"])   # preflight: fail early
    llm = llm or (MockLLM() if os.environ.get("SIM_MOCK_LLM") == "1" else LlamaServer(cfg))
    store = Store(db_path or ROOT / "data" / "study.db")
    eng = Engine(cfg, personas, store, llm)
    app = FastAPI(title="Training simulation", docs_url=None, redoc_url=None)
    app.state.engine = eng

    @app.get("/api/personas")
    def personas_list():
        return [{"id": p["id"], "name": p["name"], "context_line": p["context_line"]} for p in personas.values()]

    @app.post("/api/session")
    def start(r: StartReq):
        try:
            return eng.start_session(r.participant_id[:40], r.persona_id, r.consent, r.age_confirmed,
                                     cfg["study"]["consent_version"])
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except KeyError:
            raise HTTPException(404, "unknown persona")

    @app.get("/api/session/{sid}")
    def status(sid: str):
        s = store.session(sid)
        if not s:
            raise HTTPException(404)
        return {"ended": s["ended_at"] is not None, "reason": s["end_reason"], "remaining": eng.remaining(sid)}

    @app.post("/api/session/{sid}/message")
    async def message(sid: str, r: MsgReq):
        try:
            return await eng.handle_message(sid, r.text)
        except KeyError:
            raise HTTPException(404)

    @app.post("/api/session/{sid}/stop")
    def stop(sid: str):
        if not store.session(sid):
            raise HTTPException(404)
        return eng.stop(sid)

    @app.get("/api/session/{sid}/debrief")
    async def debrief(sid: str):
        s = store.session(sid)
        if not s:
            raise HTTPException(404)
        if s["ended_at"] is None:
            raise HTTPException(409, "session still running")
        try:
            return await build_debrief(eng, sid, llm)
        except HelplinesStale as e:
            raise HTTPException(503, str(e))

    @app.delete("/api/participant/{pid}")
    def delete(pid: str):
        return {"deleted_sessions": store.delete_participant(pid)}

    fe = ROOT / "frontend"
    app.mount("/static", StaticFiles(directory=fe), name="static")

    @app.get("/")
    def index():
        return FileResponse(fe / "index.html")

    return app
