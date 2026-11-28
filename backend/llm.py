"""LLM clients. CloudLLM = any OpenAI-compatible cloud API (Hyperbolic by default); LlamaServer = local llama.cpp; MockLLM = tests/CI."""
import asyncio
import itertools
import re
import time
import httpx

from .config import get_api_key, provider

_THINK = re.compile(r"<think>.*?</think>", re.S)


class Reply(str):
    """Model text that also carries why generation stopped ('length' = cut off by the token limit)."""
    finish = None

    def __new__(cls, text, finish=None):
        o = super().__new__(cls, text)
        o.finish = finish
        return o


class LLMError(Exception):
    """Model service problem with a message that is safe to show/log (never contains the API key)."""


def _error_message(r: httpx.Response) -> str:
    """Providers differ: {"error": "text"}, {"error": {"message": "text"}} (OpenAI style) or {"message": "text"}."""
    try:
        j = r.json()
        e = j.get("error", j.get("message", "")) if isinstance(j, dict) else ""
    except Exception:
        return r.text[:160]
    return str(e.get("message", "") if isinstance(e, dict) else e)[:200]


OPTIONAL_PARAMS = ("top_k", "top_p", "repetition_penalty", "presence_penalty", "frequency_penalty")


class CloudLLM:
    """OpenAI-compatible chat completions over HTTPS (config section `model.<provider>`, default `model.hyperbolic`).
    Retries 429/5xx/timeouts with backoff, spaces requests, tries fallback models, injects the human-simulation system block,
    and drops optional sampling parameters the provider rejects (then remembers that)."""

    def __init__(self, cfg: dict, key: str | None = None, transport=None):
        name = provider(cfg)
        o = cfg["model"][name]
        self.name = o.get("display_name", name.capitalize())
        self.url = o["base_url"].rstrip("/")
        self.models = [o["model"], *o.get("fallback_models", [])]
        self.key_env = o.get("key_env", "HYPERBOLIC_API_KEY")
        self.key = key or get_api_key(self.key_env)
        self.dropped: set[str] = set()
        self.s = cfg["sampling"]
        self.prefix = " ".join((o.get("system_prefix") or "").split())
        self.min_interval, self.retries = float(o.get("min_interval_s", 0.3)), int(o.get("max_retries", 3))
        self.timeout = float(o.get("timeout_s", 120))
        self.transport, self._lock, self._last, self._ok_until = transport, asyncio.Lock(), 0.0, 0.0
        self.last_model = None

    def _client(self):
        return httpx.AsyncClient(timeout=self.timeout, transport=self.transport)

    def _headers(self):
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    async def health(self) -> bool:
        """Key present and accepted by the provider (GET /models), cached for 60 s. Does not prove there are credits."""
        if not self.key:
            return False
        if time.time() < self._ok_until:
            return True
        try:
            async with self._client() as c:
                r = await c.get(self.url + "/models", headers=self._headers())
            ok = r.status_code == 200
        except Exception:
            ok = False
        self._ok_until = time.time() + 60 if ok else 0.0
        return ok

    def _with_prefix(self, messages):
        """Inject the human-simulation block into the request itself (merged into the first system message)."""
        if not self.prefix:
            return messages
        if messages and messages[0].get("role") == "system":
            return [{"role": "system", "content": self.prefix + "\n\n" + messages[0]["content"]}, *messages[1:]]
        return [{"role": "system", "content": self.prefix}, *messages]

    def _body(self, model, messages, boost, max_tokens=None):
        s = self.s
        body = {"model": model, "messages": self._with_prefix(messages), "temperature": s["temperature"], "stream": False,
                "max_tokens": min(max_tokens or s["max_tokens"], s["max_tokens"])}
        for k in ("top_p", "top_k"):
            if k in s:
                body[k] = s[k]
        body["presence_penalty"] = min(2.0, s.get("presence_penalty", 0) + boost)
        body["frequency_penalty"] = min(2.0, s.get("frequency_penalty", 0) + 2 * boost)
        if "repeat_penalty" in s:
            body["repetition_penalty"] = round(s["repeat_penalty"] + boost, 3)
        for k in self.dropped:
            body.pop(k, None)
        return body

    async def generate(self, messages, penalty_boost: float = 0.0, seed=None, max_tokens=None) -> str:
        if not self.key:
            raise LLMError(f"{self.name} API key missing. Put {self.key_env}=... in the .env file (see .env.example).")
        last_err = "no response"
        for model in self.models:
            attempt = 0
            while attempt <= self.retries:
                async with self._lock:                                # one request at a time, spaced out (rate limits)
                    wait = self._last + self.min_interval - time.time()
                    if wait > 0:
                        await asyncio.sleep(wait)
                    try:
                        async with self._client() as c:
                            r = await c.post(self.url + "/chat/completions", headers=self._headers(),
                                             json=self._body(model, messages, penalty_boost, max_tokens))
                    except (httpx.TimeoutException, httpx.TransportError) as e:
                        r, last_err = None, f"network problem ({type(e).__name__})"
                    finally:
                        self._last = time.time()
                retry_after = None
                if r is not None:
                    if r.status_code == 200:
                        d = r.json()
                        if d.get("choices"):
                            self.last_model = model
                            text = d["choices"][0]["message"].get("content") or ""
                            return Reply(_THINK.sub("", text).split("</think>")[-1].strip(), d["choices"][0].get("finish_reason"))
                        last_err = f"model returned no choices: {_error_message(r)[:120]}"
                    else:
                        msg = _error_message(r)
                        if r.status_code == 401:
                            raise LLMError(f"{self.name} rejected the API key (401). Check {self.key_env}.")
                        if r.status_code == 402:
                            raise LLMError(f"{self.name}: insufficient credits and no active subscription (402). {msg[:140]}")
                        if r.status_code in (400, 422):
                            bad = [k for k in OPTIONAL_PARAMS if k in msg.lower() and k not in self.dropped]
                            if bad:                                   # provider dislikes an optional parameter: drop it, retry same model
                                self.dropped.update(bad)
                                last_err = f"dropped unsupported parameter(s) {bad}"
                                continue
                        if r.status_code in (400, 404, 422):
                            last_err = f"HTTP {r.status_code} for model {model}: {msg}"
                            break                                     # not retryable here; try the next fallback model
                        last_err = f"HTTP {r.status_code}: {msg}"
                        try:
                            retry_after = float(r.headers.get("retry-after", ""))
                        except ValueError:
                            retry_after = None
                if attempt < self.retries:
                    await asyncio.sleep(min(20.0, retry_after if retry_after else 1.5 * 2 ** attempt))
                attempt += 1
        raise LLMError(f"{self.name} request failed: {last_err}")


def create_llm(cfg: dict):
    return LlamaServer(cfg) if provider(cfg) == "local" else CloudLLM(cfg)


class LlamaServer:
    def __init__(self, cfg: dict):
        ls, self.sampling = cfg["llama_server"], cfg["sampling"]
        self.url = f"http://{ls['host']}:{ls['port']}/v1/chat/completions"
        self.no_think = cfg["model"].get("chat_template_no_think", True)

    async def generate(self, messages, penalty_boost: float = 0.0, seed=None, max_tokens=None) -> str:
        s = self.sampling
        body = {"messages": messages, "temperature": s["temperature"], "min_p": s["min_p"],
                "repeat_penalty": s["repeat_penalty"] + penalty_boost, "presence_penalty": s.get("presence_penalty", 0),
                "max_tokens": min(max_tokens or s["max_tokens"], s["max_tokens"]), "stream": False}
        for k in ("top_p", "top_k", "frequency_penalty"):
            if k in s:
                body[k] = s[k]
        if seed is not None:
            body["seed"] = seed
        if self.no_think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(self.url, json=body)
            r.raise_for_status()
            ch = r.json()["choices"][0]
            return Reply(_THINK.sub("", ch["message"]["content"]).split("</think>")[-1].strip(), ch.get("finish_reason"))


class MockLLM:
    """Scripted replies; cycles. Used by tests/CI."""
    def __init__(self, replies=None, delay: float = 0.0):
        self.replies = replies or ["hey, how's your day going?", "nice, what do you do for fun?",
                                   "ha that's cool, tell me more", "i get that, same here honestly"]
        self._it = itertools.cycle(self.replies)
        self.delay = delay
        self.calls = 0

    async def generate(self, messages, penalty_boost: float = 0.0, seed=None, max_tokens=None) -> str:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return next(self._it)
