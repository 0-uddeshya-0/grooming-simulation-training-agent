"""Check the cloud model setup end to end with ONE tiny request per model: prints the base URL, the exact model ID sent in the
JSON body, the HTTP status and the provider's answer. Needs the API key (HYPERBOLIC_API_KEY in the environment or .env).
Run:  python scripts/check_model.py      (a 402 means the key works but the account has no credits/subscription)"""
import asyncio, json, sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import load_app, provider
from backend.llm import CloudLLM, LLMError

cfg = load_app()
if provider(cfg) == "local":
    sys.exit("model.provider is 'local' in config/app.yaml; this script checks the cloud provider")
log = []
async def on_request(req): log.append({"url": str(req.url), "body": json.loads(req.content) if req.content else None})
async def on_response(resp): await resp.aread(); log[-1].update(status=resp.status_code, text=resp.text[:300])
async def main():
    llm = CloudLLM(cfg); llm.retries = 0           # one attempt per model, so fallbacks appear as separate requests
    llm._client = lambda: httpx.AsyncClient(timeout=120, event_hooks={"request": [on_request], "response": [on_response]})
    print(f"provider {llm.name}, base URL {llm.url}, models {llm.models}")
    try:
        print("reply:", repr(await llm.generate([{"role": "user", "content": "Hello! Introduce yourself in one short sentence."}])))
    except LLMError as e:
        print("FAILED:", e)
    for e in log:
        b = e["body"] or {}
        sysm = next((m["content"] for m in b.get("messages", []) if m["role"] == "system"), "")
        print(f"{e['url']}\n  model in JSON body : {b.get('model')!r}\n  system block sent  : {sysm[:70]!r}...\n  HTTP status        : {e.get('status')}\n  response           : {e.get('text')}")
asyncio.run(main())
