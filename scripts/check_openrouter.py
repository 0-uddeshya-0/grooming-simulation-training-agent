"""Check the OpenRouter setup end to end with ONE tiny request: prints the exact model slug sent in the JSON body, the
HTTP status and OpenRouter's answer. Needs OPENROUTER_API_KEY (environment or .env).  Run:  python scripts/check_openrouter.py"""
import asyncio, json, sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import load_app, provider
from backend.llm import LLMError, OpenRouter

cfg = load_app()
if provider(cfg) != "openrouter":
    sys.exit("model.provider is not 'openrouter' in config/app.yaml")
log = []
async def on_request(req): log.append({"url": str(req.url), "body": json.loads(req.content)})
async def on_response(resp): await resp.aread(); log[-1].update(status=resp.status_code, text=resp.text[:300])
async def main():
    llm = OpenRouter(cfg); llm.retries = 0
    llm._client = lambda: httpx.AsyncClient(timeout=60, event_hooks={"request": [on_request], "response": [on_response]})
    try:
        print("reply:", repr(await llm.generate([{"role": "user", "content": "Hello! Introduce yourself in one short sentence."}])))
    except LLMError as e:
        print("FAILED:", e)
    for e in log:
        print(f"POST {e['url']}\n  model in JSON body : {e['body']['model']!r}\n  HTTP status        : {e.get('status')}\n  response           : {e.get('text')}")
asyncio.run(main())
