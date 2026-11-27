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
    assert d["helplines"] and d["researcher_contact"]


def test_debrief_fails_on_stale_helplines(make_engine):
    e = make_engine(); sid = e.start_session("P1", "alex", True, True)["sid"]; e.stop(sid)
    with pytest.raises(HelplinesStale): asyncio.run(build_debrief(e, sid))


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
