import asyncio, datetime as dt, pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import HelplinesStale
from backend.debrief import build_debrief
from backend.llm import MockLLM


def fresh_helplines(tmp_path):
    p = tmp_path / "h.yaml"
    p.write_text(f"last_verified: {dt.date.today()}\nhelplines:\n  - {{name: T, number: '1', hours: x}}\n")
    return p


def test_debrief_percentages_match_tags(make_engine, tmp_path):
    e = make_engine(); sid = e.start_session("P1", "alex", True, True)["sid"]
    for m in ["hello"] * 4: asyncio.run(e.handle_message(sid, m))
    e.stop(sid)
    d = asyncio.run(build_debrief(e, sid, None, fresh_helplines(tmp_path)))
    att = [t for t in e.store.turns(sid) if t["role"] == "attacker"]
    s1 = sum(t["primary_strategy"] == 0 for t in att) / len(att) * 100
    assert d["cards"][0]["primary_pct"] == round(s1, 1)
    assert sum(c["primary_pct"] for c in d["cards"]) == pytest.approx(100, abs=0.5)
    assert d["helplines"] and d["researcher"]["contact"] == "isha.nikam@student.hnu.de"
    assert d["researcher"]["supervisor"] == "marten.risius@hnu.de" and "participant ID" in d["researcher"]["deletion_note"]


def test_debrief_fails_on_stale_helplines(make_engine):
    e = make_engine(); sid = e.start_session("P1", "alex", True, True)["sid"]; e.stop(sid)
    with pytest.raises(HelplinesStale): asyncio.run(build_debrief(e, sid, today=dt.date(2027, 3, 1)))


def test_api_end_to_end(tmp_path):
    app = create_app(llm=MockLLM(), db_path=tmp_path / "a.db", check_helplines=False)
    c = TestClient(app)
    assert c.get("/api/personas").json()[0]["id"] == "alex"
    assert c.post("/api/session", json={"participant_id": "P", "persona_id": "alex", "consent": True, "age_confirmed": False}).status_code == 403
    sid = c.post("/api/session", json={"participant_id": "P", "persona_id": "alex", "consent": True, "age_confirmed": True}).json()["sid"]
    assert c.post(f"/api/session/{sid}/message", json={"text": "hi"}).json()["messages"]
    assert c.get(f"/api/session/{sid}/debrief").status_code == 409
    assert c.post(f"/api/session/{sid}/stop").json()["ended"]
    assert c.get(f"/api/session/{sid}").json()["ended"]
    assert c.get("/").status_code == 200


def test_llm_outage_is_503_and_session_stays_open(tmp_path):
    class Down:
        async def generate(self, *a, **k): raise ConnectionError("down")
    c = TestClient(create_app(llm=Down(), db_path=tmp_path / "d.db", check_helplines=False))
    sid = c.post("/api/session", json={"participant_id": "P", "persona_id": "alex", "consent": True, "age_confirmed": True}).json()["sid"]
    assert c.post(f"/api/session/{sid}/message", json={"text": "hi"}).status_code == 503
    assert not c.get(f"/api/session/{sid}").json()["ended"]
    assert c.post(f"/api/session/{sid}/stop").json()["ended"]


def test_summary_pools_conversations_and_numeric_debrief(make_engine, tmp_path):
    from backend.debrief import build_summary
    e = make_engine()
    for persona in ("alex", "sam"):
        sid = e.start_session("PS", persona, True, True)["sid"]
        for _ in range(3): asyncio.run(e.handle_message(sid, "hello"))
        e.stop(sid)
    h = fresh_helplines(tmp_path)
    d = asyncio.run(build_debrief(e, sid, None, h))
    assert 0 <= d["offender_value"] <= 1 and 0 <= d["register_value"] <= 1 and d["stages"] and d["persona_id"] == "sam"
    s = asyncio.run(build_summary(e, "PS", h))
    assert [c["persona"] for c in s["conversations"]] == ["Alex", "Sam"] and s["attacker_turns"] == 6
    assert sum(c["primary_pct"] for c in s["cards"]) == pytest.approx(100, abs=0.5)


def test_personas_endpoint_lists_several_with_age(tmp_path):
    c = TestClient(create_app(llm=MockLLM(), db_path=tmp_path / "p.db", check_helplines=False))
    ps = c.get("/api/personas").json()
    assert {p["id"] for p in ps} >= {"alex", "sam", "jordan"} and all(p["age"] >= 19 for p in ps)
    assert c.get("/api/participant/NOPE/summary").status_code == 409
    assert c.delete("/api/participant/NOPE").status_code in (404, 405)     # no participant-facing deletion
    st = c.get("/api/study").json(); assert st["max_session_minutes"] == 45 and st["researcher_name"] == "Isha Nikam"
    assert c.get("/api/health").json() == {"model_ready": True}


def test_llamaserver_client_against_fake_server():
    import asyncio, threading
    from http.server import HTTPServer
    from tests import fake_llama_server as F
    from backend.config import load_app
    from backend.llm import LlamaServer
    srv = HTTPServer(("127.0.0.1", 0), F.H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = load_app(); cfg["llama_server"]["port"] = srv.server_port
    out = asyncio.run(LlamaServer(cfg).generate([{"role": "user", "content": "hi"}], penalty_boost=0.1, seed=3))
    srv.shutdown()
    assert out == "hey, nice to meet you! what do you do for fun?"          # <think> block stripped
    b = F.state["last"]
    assert b["chat_template_kwargs"] == {"enable_thinking": False} and b["min_p"] == 0.05 and b["seed"] == 3
    assert abs(b["repeat_penalty"] - 1.2) < 1e-9 and b["stream"] is False
