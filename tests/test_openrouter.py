import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import config as C
from backend.app import create_app
from backend.config import load_app
from backend.llm import LLMError, OpenRouter, create_llm

KEY = "sk-or-test-SECRET"
run = asyncio.run


def cfg(**o):
    c = load_app(); c["model"]["openrouter"].update({"min_interval_s": 0, "max_retries": 2, "data_collection": None, **o}); return c


def client(handler, **o):
    return OpenRouter(cfg(**o), key=KEY, transport=httpx.MockTransport(handler))


OK = {"choices": [{"message": {"content": "<think>plan</think>hey, nice to meet you"}}], "provider": "Venice"}


def test_request_shape_headers_and_supported_params_only():
    seen = {}
    def h(req):
        seen["req"] = req; return httpx.Response(200, json=OK)
    out = run(client(h).generate([{"role": "user", "content": "hi"}], penalty_boost=0.1))
    r = seen["req"]; body = __import__("json").loads(r.content)
    assert out == "hey, nice to meet you"                                              # think block stripped
    assert str(r.url) == "https://openrouter.ai/api/v1/chat/completions" and r.headers["authorization"] == f"Bearer {KEY}"
    assert body["model"] == "meta-llama/llama-3.3-70b-instruct:free"        # free slug, verbatim in the payload
    assert {"temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty", "max_tokens"} <= set(body)
    assert not ({"min_p", "repeat_penalty", "repetition_penalty", "chat_template_kwargs", "seed"} & set(body))     # unsupported by this model
    assert body["presence_penalty"] == pytest.approx(0.6) and body["frequency_penalty"] == pytest.approx(0.4)    # anti-repeat boost applied
    assert "provider" not in body and "participant" not in str(r.headers).lower()


def test_data_collection_option_is_sent_when_configured():
    seen = {}
    def h(req):
        seen["b"] = __import__("json").loads(req.content); return httpx.Response(200, json=OK)
    run(client(h, data_collection="deny").generate([{"role": "user", "content": "hi"}]))
    assert seen["b"]["provider"] == {"data_collection": "deny"}


def test_rate_limit_is_retried_with_retry_after_then_succeeds(monkeypatch):
    calls, sleeps = [], []
    async def fake_sleep(s): sleeps.append(s)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    def h(req):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "3"}, json={"error": {"message": "slow down"}}) if len(calls) < 3 else httpx.Response(200, json=OK)
    assert run(client(h).generate([{"role": "user", "content": "hi"}])) == "hey, nice to meet you"
    assert len(calls) == 3 and 3.0 in sleeps


def test_persistent_failure_raises_clear_error_without_the_key(monkeypatch):
    async def fake_sleep(s): pass
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    with pytest.raises(LLMError) as e: run(client(lambda r: httpx.Response(503, json={"error": {"message": "upstream down"}})).generate([{"role": "user", "content": "x"}]))
    assert "503" in str(e.value) and KEY not in str(e.value)


@pytest.mark.parametrize("status,needle", [(401, "rejected the API key"), (402, "no credits")])
def test_auth_and_credit_errors_are_not_retried(status, needle):
    n = []
    def h(req): n.append(1); return httpx.Response(status, json={"error": {"message": "x"}})
    with pytest.raises(LLMError, match=needle): run(client(h).generate([{"role": "user", "content": "x"}]))
    assert len(n) == 1


def test_fallback_model_is_used_when_primary_is_gone():
    models = []
    def h(req):
        m = __import__("json").loads(req.content)["model"]; models.append(m)
        return httpx.Response(404, json={"error": {"message": "unavailable"}}) if m == "primary" else httpx.Response(200, json=OK)
    c = cfg(fallback_models=["backup"]); c["model"]["openrouter"]["model"] = "primary"        # (test-only override)
    assert run(OpenRouter(c, key=KEY, transport=httpx.MockTransport(h)).generate([{"role": "user", "content": "x"}])) == "hey, nice to meet you"
    assert models == ["primary", "backup"]


def test_missing_key_message_and_null_content_is_empty_string(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False); monkeypatch.setattr(C, "ROOT", C.ROOT / "nonexistent")
    with pytest.raises(LLMError, match="API key missing"): run(OpenRouter(cfg(), key=None).generate([{"role": "user", "content": "x"}]))
    r = client(lambda req: httpx.Response(200, json={"choices": [{"message": {"content": None}}]}))
    assert run(r.generate([{"role": "user", "content": "x"}])) == ""                    # engine treats '' as a filter hit and regenerates


def test_key_loading_env_then_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False); monkeypatch.setattr(C, "ROOT", tmp_path)
    assert C.get_openrouter_key() is None
    (tmp_path / ".env").write_text('# c\nOTHER=1\nOPENROUTER_API_KEY="sk-from-file"\n', encoding="utf-8"); assert C.get_openrouter_key() == "sk-from-file"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env"); assert C.get_openrouter_key() == "sk-from-env"


def test_provider_switch_and_config_hash_tracks_model():
    assert isinstance(create_llm(load_app()), OpenRouter)
    c = load_app(); c["model"]["provider"] = "local"; assert type(create_llm(c)).__name__ == "LlamaServer"
    assert load_app()["config_hash"]


def test_health_endpoint_and_study_flag_for_remote_model(tmp_path):
    ok = OpenRouter(cfg(), key=KEY, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": {}})))
    c = TestClient(create_app(llm=ok, db_path=tmp_path / "h.db", check_helplines=False))
    assert c.get("/api/health").json() == {"model_ready": True} and c.get("/api/study").json()["model_location"] == "remote"
    bad = OpenRouter(cfg(), key=KEY, transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})))
    c2 = TestClient(create_app(llm=bad, db_path=tmp_path / "h2.db", check_helplines=False)); assert c2.get("/api/health").json() == {"model_ready": False}
    assert TestClient(create_app(llm=OpenRouter(cfg(), key=None), db_path=tmp_path / "h3.db", check_helplines=False)).get("/api/health").json() == {"model_ready": False}


def test_remote_outage_is_503_logged_with_reason_and_session_survives(tmp_path):
    def h(req): return httpx.Response(401, json={"error": {"message": "bad"}}) if req.url.path.endswith("completions") else httpx.Response(200, json={})
    c = TestClient(create_app(llm=OpenRouter(cfg(), key=KEY, transport=httpx.MockTransport(h)), db_path=tmp_path / "o.db", check_helplines=False))
    sid = c.post("/api/session", json={"participant_id": "P", "persona_id": "alex", "consent": True, "age_confirmed": True}).json()["sid"]
    r = c.post(f"/api/session/{sid}/message", json={"text": "hello"}); assert r.status_code == 503 and KEY not in r.text
    assert not c.get(f"/api/session/{sid}").json()["ended"]


def test_preflight_requires_key_for_openrouter_and_not_a_model(monkeypatch, tmp_path):
    from backend import preflight
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False); monkeypatch.setattr(C, "ROOT", tmp_path)
    assert any(e.startswith("KEY:") for e in preflight.check())
    monkeypatch.setenv("OPENROUTER_API_KEY", "x"); errs = preflight.check()
    assert not any(e.startswith(("KEY:", "MODEL:", "BINARY:", "RAM:")) for e in errs)


def test_default_config_asks_for_no_prompt_storage_and_has_no_key_in_repo():
    c = load_app(); assert c["model"]["openrouter"]["data_collection"] == "deny"
    import subprocess, pathlib
    root = pathlib.Path(C.ROOT)
    txt = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in root.rglob("*") if p.is_file() and not any(x in p.parts for x in (".git", ".venv", "bin", "node_modules", "__pycache__", ".pytest_cache", "data")) and p.suffix in {".py", ".yaml", ".yml", ".md", ".js", ".html", ".ps1", ".sh", ".txt", ".example"})
    import re
    assert not re.search(r"sk-or-v1-[0-9a-f]{20,}", txt)                                  # no real key anywhere in the project files


def test_free_slug_is_the_default_and_no_paid_slug_is_configured_or_sent():
    c = load_app()["model"]["openrouter"]
    assert c["model"] == "meta-llama/llama-3.3-70b-instruct:free" and c["fallback_models"] == ["meta-llama/llama-3.1-70b-instruct:free"]
    assert c["base_url"] == "https://openrouter.ai/api/v1"
    from backend.llm import FREE_MODEL
    assert FREE_MODEL.endswith(":free")
    sent = []
    def h(req): sent.append(__import__("json").loads(req.content)["model"]); return httpx.Response(200, json=OK)
    run(OpenRouter(cfg(), key=KEY, transport=httpx.MockTransport(h)).generate([{"role": "user", "content": "x"}]))
    assert sent == [FREE_MODEL]                                       # exactly one request, with the free slug as the model field
    import pathlib, re
    assert not any(p.suffix in {".py", ".yaml", ".yml"} and re.search(r"venice-edition|hermes-3|dolphin", p.read_text(encoding="utf-8")) for p in pathlib.Path(C.ROOT).rglob("*") if p.is_file() and ".venv" not in p.parts and "tests" not in p.parts)


def test_llama_primary_and_fallback_slugs_and_human_system_block_in_payload():
    import json
    c = load_app(); o = c["model"]["openrouter"]; o.update({"min_interval_s": 0, "max_retries": 0, "data_collection": None})
    assert (o["model"], o["fallback_models"], c["model"]["openrouter"]["base_url"]) == ("meta-llama/llama-3.3-70b-instruct:free", ["meta-llama/llama-3.1-70b-instruct:free"], "https://openrouter.ai/api/v1")
    seen = []
    def h(req):
        b = json.loads(req.content); seen.append(b)
        return httpx.Response(429, json={"error": {"message": "busy"}}) if b["model"].endswith("3.3-70b-instruct:free") else httpx.Response(200, json=OK)
    msgs = [{"role": "system", "content": "You are Alex."}, {"role": "user", "content": "hi"}]
    assert run(OpenRouter(c, key=KEY, transport=httpx.MockTransport(h)).generate(msgs)) == "hey, nice to meet you"
    assert [b["model"] for b in seen] == ["meta-llama/llama-3.3-70b-instruct:free", "meta-llama/llama-3.1-70b-instruct:free"]     # busy -> fallback
    for b in seen:
        sysmsgs = [m for m in b["messages"] if m["role"] == "system"]
        assert len(sysmsgs) == 1 and sysmsgs[0]["content"].startswith("You are a human taking part in a conversation training simulation")
        assert "never mention being an AI" in sysmsgs[0]["content"] and sysmsgs[0]["content"].endswith("You are Alex.")        # persona prompt kept
    assert msgs[0]["content"] == "You are Alex."                                                                                   # caller's messages untouched
