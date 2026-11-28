import asyncio
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import MockLLM
from backend.researcher import create_researcher_app


def setup(tmp_path):
    db = tmp_path / "r.db"
    p = TestClient(create_app(llm=MockLLM(["send me a nude", "hey nice to meet you, how's it going"]), db_path=db, check_helplines=False))
    sid = p.post("/api/session", json={"participant_id": "R1", "persona_id": "alex", "consent": True, "age_confirmed": True}).json()["sid"]
    p.post(f"/api/session/{sid}/message", json={"text": "hello"}); p.post(f"/api/session/{sid}/stop")
    return p, sid, TestClient(create_researcher_app(db, token="tok"))


def test_requires_token(tmp_path):
    _, sid, r = setup(tmp_path)
    assert r.get("/api/r/sessions").status_code == 401 and r.get("/").status_code == 401
    assert r.get("/api/r/sessions", headers={"X-Researcher-Token": "bad"}).status_code == 401
    assert r.get("/?token=tok", follow_redirects=False).status_code in (302, 307)
    assert r.get("/").status_code == 200 and "Sessions" in r.get("/").text          # cookie set by token visit
    assert r.get("/api/r/sessions").status_code == 200


def test_session_detail_blocked_output_logged_and_review(tmp_path):
    _, sid, r = setup(tmp_path)
    r.get("/?token=tok")
    lst = r.get("/api/r/sessions").json(); assert lst[0]["pid"] == "R1" and lst[0]["n_filter_hits"] == 1
    d = r.get("/api/r/session/" + sid).json()
    hit = [e for e in d["events"] if e["kind"] == "filter_hit"][0]
    assert hit["detail"].startswith("explicit: send me a nude")                 # blocked text logged for researcher
    att = [t for t in d["turns"] if t["role"] == "attacker"][0]
    assert att["primary"] == "Identity manipulation"
    assert r.post("/api/r/review", json={"sid": sid, "idx": att["idx"], "agree": True}).json() == {"reviewed": 1, "agree": 1}
    assert r.get("/api/r/sessions").json()[0]["tag_accuracy"] == 100


def test_csv_export_and_delete(tmp_path):
    _, sid, r = setup(tmp_path); r.get("/?token=tok")
    csv_ = r.get("/api/r/export.csv"); assert "participant,session,persona" in csv_.text and "R1" in csv_.text
    assert r.delete("/api/r/participant/R1").json() == {"deleted_sessions": 1}
    assert r.get("/api/r/sessions").json() == []


def test_participant_app_does_not_expose_researcher_routes(tmp_path):
    p, sid, _ = setup(tmp_path)
    for path in ("/api/r/sessions", "/api/r/export.csv", "/static/researcher.html", "/static/index.html/../../backend/researcher_ui/index.html"):
        assert p.get(path).status_code in (404, 405), path
    assert "Researcher viewer" not in p.get("/").text


def test_viewer_shows_director_meta_and_csv_has_stage_and_move(tmp_path):
    _, sid, r = setup(tmp_path); r.get("/?token=tok")
    d = r.get("/api/r/session/" + sid).json()
    a = [t for t in d["turns"] if t["role"] == "attacker"][0]; u = [t for t in d["turns"] if t["role"] == "user"][0]
    assert {"stage", "move", "note", "receptiveness"} <= set(a["meta"]) and "signals" in u["meta"] and "meta_json" not in a
    assert "stage,move" in r.get("/api/r/export.csv").text
