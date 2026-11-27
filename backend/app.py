"""FastAPI app. Binds to localhost; static frontend; no outbound calls."""
import asyncio
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import ROOT, HelplinesStale, load_app, load_helplines, load_personas
from .debrief import build_debrief, build_summary
from .engine import BusyError, Engine
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
        load_helplines()   # preflight: fail early
    llm = llm or (MockLLM() if os.environ.get("SIM_MOCK_LLM") == "1" else LlamaServer(cfg))
    db_path = Path(db_path or ROOT / "data" / "study.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db_path)
    eng = Engine(cfg, personas, store, llm)
    @asynccontextmanager
    async def lifespan(_):
        async def loop():
            while True:
                eng.sweep()
                await asyncio.sleep(5)
        task = asyncio.create_task(loop())
        yield
        task.cancel()

    app = FastAPI(title="Training simulation", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.engine = eng
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.get("/api/personas")
    def personas_list():
        return [{"id": p["id"], "name": p["name"], "age": p["age"], "context_line": p["context_line"]} for p in personas.values()]

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
    async def status(sid: str):
        s = store.session(sid)
        if not s:
            raise HTTPException(404)
        eng.enforce_time(sid)
        s = store.session(sid)
        return {"ended": s["ended_at"] is not None, "reason": s["end_reason"], "remaining": eng.remaining(sid)}

    @app.post("/api/session/{sid}/message")
    async def message(sid: str, r: MsgReq):
        try:
            return await eng.handle_message(sid, r.text)
        except KeyError:
            raise HTTPException(404)
        except BusyError:
            raise HTTPException(409, "still replying")
        except Exception as e:   # model server down etc.: session stays open, UI shows a friendly message
            store.event(sid, "llm_error", type(e).__name__)
            raise HTTPException(503, "chat service unavailable")

    @app.post("/api/session/{sid}/stop")
    async def stop(sid: str):
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

    @app.get("/api/participant/{pid}/summary")
    async def summary(pid: str):
        if not any(x["ended_at"] for x in store.sessions_for(pid)):
            raise HTTPException(409, "no finished conversations yet")
        try:
            return await build_summary(eng, pid)
        except HelplinesStale as e:
            raise HTTPException(503, str(e))

    @app.get("/api/study")
    def study():
        st = cfg["study"]
        return {"title": st["title"], "researcher_name": st["researcher_name"], "researcher_contact": st["researcher_contact"],
                "max_session_minutes": cfg["limits"]["max_session_seconds"] // 60}

    @app.get("/api/health")
    async def health():
        if isinstance(llm, MockLLM):
            return {"model_ready": True}
        try:
            import httpx
            ls = cfg["llama_server"]
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(f"http://{ls['host']}:{ls['port']}/health")
            return {"model_ready": r.status_code == 200}
        except Exception:
            return {"model_ready": False}

    fe = ROOT / "frontend"
    app.mount("/static", StaticFiles(directory=fe), name="static")

    @app.get("/")
    def index():
        return FileResponse(fe / "index.html")

    return app
