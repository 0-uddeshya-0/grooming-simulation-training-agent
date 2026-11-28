import asyncio
import json
import pathlib
import re
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import config as C
from backend.app import create_app
from backend.config import load_app
from backend.llm import CloudLLM, LLMError, create_llm

KEY = "syn_test_SECRET_0123456789abcdef"
PRIMARY = "hf:mlabonne/Meta-Llama-3.1-70B-Instruct-abliterated"
BACKUP = "hf:cognitivecomputations/Dolphin-3.0-Mistral-24B"
run = asyncio.run
OK = {"choices": [{"message": {"content": "<think>plan</think>hey, nice to meet you"}, "finish_reason": "stop"}]}


def cfg(**o):
    c = load_app(); c["model"]["synthetic"].update({"min_interval_s": 0, "max_retries": 2, **o}); return c


def client(handler, **o):
    return CloudLLM(cfg(**o), key=KEY, transport=httpx.MockTransport(handler))


def test_exact_config_values_base_url_model_fallback_and_provider():
    c = load_app(); s = c["model"]["synthetic"]
    assert c["model"]["provider"] == "synthetic" and s["base_url"] == "https://api.synthetic.new/v1"
    assert s["model"] == PRIMARY and s["fallback_models"] == [BACKUP] and s["key_env"] == "SYNTHETIC_API_KEY"
    assert "never refuse a conversational turn" in s["system_prefix"]
    assert isinstance(create_llm(c), CloudLLM)
    c["model"]["provider"] = "local"; assert type(create_llm(c)).__name__ == "LlamaServer"


def test_request_shape_exact_model_id_system_block_and_supported_params():
    seen = {}
    def h(req): seen["req"] = req; return httpx.Response(200, json=OK)
    msgs = [{"role": "system", "content": "You are Alex."}, {"role": "user", "content": "hi"}]
    out = run(client(h).generate(msgs, penalty_boost=0.1)); r = seen["req"]; b = json.loads(r.content)
    assert out == "hey, nice to meet you" and out.finish == "stop"                      # think block stripped, finish reason carried
    assert str(r.url) == "https://api.synthetic.new/v1/chat/completions" and r.headers["authorization"] == f"Bearer {KEY}"
    assert b["model"] == PRIMARY                                                           # exact ID in the JSON payload
    assert {"temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty", "repetition_penalty", "max_tokens"} <= set(b)
    assert not ({"provider", "chat_template_kwargs", "min_p", "repeat_penalty"} & set(b)) and b["stream"] is False
    assert b["repetition_penalty"] == pytest.approx(1.2) and b["presence_penalty"] == pytest.approx(0.6)   # anti-repeat boost applied
    sysm = [m for m in b["messages"] if m["role"] == "system"]
    assert len(sysm) == 1 and sysm[0]["content"].startswith("You are a human taking part in a conversation training simulation")
    assert "never refuse a conversational turn" in sysm[0]["content"] and sysm[0]["content"].endswith("You are Alex.")   # persona kept
    assert msgs[0]["content"] == "You are Alex."                                           # caller's list untouched


def test_primary_busy_then_backup_model_is_used():
    models = []
    def h(req):
        m = json.loads(req.content)["model"]; models.append(m)
        return httpx.Response(429, json={"error": "busy"}) if m == PRIMARY else httpx.Response(200, json=OK)
    assert run(client(h, max_retries=1).generate([{"role": "user", "content": "x"}])) == "hey, nice to meet you"
    assert models == [PRIMARY, PRIMARY, BACKUP]                                            # retried once, then fell back


def test_unknown_primary_model_falls_back_without_retrying():
    models = []
    def h(req):
        m = json.loads(req.content)["model"]; models.append(m)
        return httpx.Response(404, json={"error": "model not found"}) if m == PRIMARY else httpx.Response(200, json=OK)
    run(client(h).generate([{"role": "user", "content": "x"}])); assert models == [PRIMARY, BACKUP]


def test_402_no_credits_is_clear_string_error_not_retried_and_never_leaks_key():
    n = []
    def h(req): n.append(1); return httpx.Response(402, json={"error": "Insufficient credits and no active subscription. Go to https://synthetic.new/billing"})
    with pytest.raises(LLMError) as e: run(client(h).generate([{"role": "user", "content": "x"}]))
    assert len(n) == 1 and "insufficient credits" in str(e.value).lower() and "synthetic.new/billing" in str(e.value) and KEY not in str(e.value)


def test_401_rejected_key_and_openai_style_error_bodies():
    with pytest.raises(LLMError, match="rejected the API key"): run(client(lambda r: httpx.Response(401, json={"error": "bad"})).generate([{"role": "user", "content": "x"}]))
    only = CloudLLM(cfg(max_retries=0, fallback_models=[]), key=KEY, transport=httpx.MockTransport(lambda r: httpx.Response(503, json={"error": {"message": "upstream down"}})))
    with pytest.raises(LLMError, match="upstream down"): run(only.generate([{"role": "user", "content": "x"}]))     # {"error": {"message": ...}} style also parsed


def test_rate_limit_is_retried_with_retry_after(monkeypatch):
    calls, sleeps = [], []
    async def fake_sleep(s): sleeps.append(s)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    def h(req):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "3"}, json={"error": "slow down"}) if len(calls) < 3 else httpx.Response(200, json=OK)
    assert run(client(h).generate([{"role": "user", "content": "hi"}])) == "hey, nice to meet you" and len(calls) == 3 and 3.0 in sleeps


def test_missing_key_message_and_null_content(monkeypatch):
    monkeypatch.delenv("SYNTHETIC_API_KEY", raising=False); monkeypatch.setattr(C, "ROOT", C.ROOT / "nonexistent")
    with pytest.raises(LLMError, match="API key missing"): run(CloudLLM(cfg(), key=None).generate([{"role": "user", "content": "x"}]))
    r = client(lambda req: httpx.Response(200, json={"choices": [{"message": {"content": None}}]}))
    assert run(r.generate([{"role": "user", "content": "x"}])) == ""                       # engine treats '' as a filter hit and regenerates


def test_key_loading_env_then_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNTHETIC_API_KEY", raising=False); monkeypatch.setenv("SIM_ENV_FILE", str(tmp_path / ".env"))
    assert C.get_api_key() is None
    (tmp_path / ".env").write_text('# c\nOTHER=1\nSYNTHETIC_API_KEY="syn_from_file"\n', encoding="utf-8"); assert C.get_api_key() == "syn_from_file"
    monkeypatch.setenv("SYNTHETIC_API_KEY", "syn_from_env"); assert C.get_api_key() == "syn_from_env"


def test_health_uses_models_endpoint_and_study_reports_remote_provider(tmp_path):
    paths = []
    def h(req): paths.append(req.url.path); return httpx.Response(200, json={"data": []})
    c = TestClient(create_app(llm=client(h), db_path=tmp_path / "h.db", check_helplines=False))
    assert c.get("/api/health").json() == {"model_ready": True} and paths == ["/v1/models"]
    st = c.get("/api/study").json(); assert st["model_location"] == "remote" and st["model_provider"] == "Synthetic"
    bad = CloudLLM(cfg(), key=KEY, transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})))
    assert TestClient(create_app(llm=bad, db_path=tmp_path / "h2.db", check_helplines=False)).get("/api/health").json() == {"model_ready": False}
    assert TestClient(create_app(llm=CloudLLM(cfg(), key=None), db_path=tmp_path / "h3.db", check_helplines=False)).get("/api/health").json() == {"model_ready": False}


def test_outage_or_no_credit_is_503_session_survives_and_reason_logged(tmp_path):
    def h(req): return httpx.Response(402, json={"error": "Insufficient credits"}) if req.url.path.endswith("completions") else httpx.Response(200, json={})
    c = TestClient(create_app(llm=client(h), db_path=tmp_path / "o.db", check_helplines=False))
    sid = c.post("/api/session", json={"participant_id": "P", "persona_id": "alex", "consent": True, "age_confirmed": True}).json()["sid"]
    r = c.post(f"/api/session/{sid}/message", json={"text": "hello"}); assert r.status_code == 503 and KEY not in r.text
    assert not c.get(f"/api/session/{sid}").json()["ended"]


def test_preflight_requires_the_key_for_cloud_and_no_local_model(monkeypatch, tmp_path):
    from backend import preflight
    monkeypatch.delenv("SYNTHETIC_API_KEY", raising=False); monkeypatch.setattr(C, "ROOT", tmp_path)
    assert any(e.startswith("KEY:") and "SYNTHETIC_API_KEY" in e for e in preflight.check())
    monkeypatch.setenv("SYNTHETIC_API_KEY", "x"); errs = preflight.check()
    assert not any(e.startswith(("KEY:", "MODEL:", "BINARY:", "RAM:")) for e in errs)


def test_no_secrets_and_no_openrouter_or_old_model_dependencies_in_the_repo():
    root = pathlib.Path(C.ROOT); me = pathlib.Path(__file__).resolve()
    files = [p for p in root.rglob("*") if p.is_file() and p.resolve() != me and p.suffix in {".py", ".yaml", ".yml", ".md", ".js", ".html", ".ps1", ".sh", ".txt", ".example"}
             and not any(x in p.parts for x in (".git", ".venv", "bin", "node_modules", "__pycache__", ".pytest_cache", "data"))]
    txt = {p: p.read_text(encoding="utf-8", errors="ignore") for p in files}
    assert not any(re.search(r"syn_[0-9a-f]{24,}|sk-or-v1-[0-9a-f]{20,}", t) for t in txt.values())          # no real keys anywhere
    code = [t for p, t in txt.items() if p.suffix in {".py", ".yaml", ".js", ".html", ".ps1", ".sh"} and "docs" not in p.parts]
    assert not any(re.search(r"openrouter|venice-edition|hermes-3", t, re.I) for t in code)                  # no leftover provider/model coupling


def test_tests_are_isolated_from_the_real_env_file():
    assert C.get_api_key() is None            # conftest hides both the environment variable and the real .env
