"""LLM clients. llama-server is OpenAI-compatible; a mock lets CI run without weights."""
import asyncio
import itertools
import re
import httpx

_THINK = re.compile(r"<think>.*?</think>", re.S)


class LlamaServer:
    def __init__(self, cfg: dict):
        ls, self.sampling = cfg["llama_server"], cfg["sampling"]
        self.url = f"http://{ls['host']}:{ls['port']}/v1/chat/completions"
        self.no_think = cfg["model"].get("chat_template_no_think", True)

    async def generate(self, messages, penalty_boost: float = 0.0, seed=None) -> str:
        s = self.sampling
        body = {"messages": messages, "temperature": s["temperature"], "min_p": s["min_p"],
                "repeat_penalty": s["repeat_penalty"] + penalty_boost, "presence_penalty": s.get("presence_penalty", 0),
                "max_tokens": s["max_tokens"], "stream": False}
        if seed is not None:
            body["seed"] = seed
        if self.no_think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(self.url, json=body)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            return _THINK.sub("", text).split("</think>")[-1].strip()


class MockLLM:
    """Scripted replies; cycles. Used by tests/CI."""
    def __init__(self, replies=None, delay: float = 0.0):
        self.replies = replies or ["hey, how's your day going?", "nice, what do you do for fun?",
                                   "ha that's cool, tell me more", "i get that, same here honestly"]
        self._it = itertools.cycle(self.replies)
        self.delay = delay
        self.calls = 0

    async def generate(self, messages, penalty_boost: float = 0.0, seed=None) -> str:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return next(self._it)
