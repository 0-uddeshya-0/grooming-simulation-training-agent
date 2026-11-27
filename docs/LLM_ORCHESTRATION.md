# LLM_ORCHESTRATION
**Serving**: `llama-server` (OpenAI-compatible, 127.0.0.1, `-c 8192`). Model, quant, sampling and the no-think switch come from `config/app.yaml`; nothing is model-specific in code.

**Prompt assembly** (`backend/prompt.py`): stable system prompt first (cache-friendly) -> last 16 turns -> a final `[DIRECTOR NOTE]` message holding the current intent, up to 3 recent user disclosures, openers to avoid, and expression hints derived from the register/offender-type scalars. The prompt describes behaviours at research level; wording is generated at runtime. It is not a safeguard (D-005).

**Sampling** (start values): temperature 0.8, min_p 0.05, repeat_penalty 1.1, presence_penalty 0.2, max_tokens 120. Tune against the repetition metric in the bake-off. Qwen3 thinking is disabled via `chat_template_kwargs.enable_thinking=false`; ``<think>...</think>` blocks are also stripped from replies before filtering.

**Per-turn pipeline** (`backend/engine.py`): STOP -> user-minor -> distress -> limit-push counter -> director.observe -> generate -> output filter (ethics ceiling rules; reasons: minor_reference, youthful_reference, explicit, meta_commentary, self_harm, pressure_or_threat, identity_request, money, meeting, roleplay; blocked text logged; <=3 regenerations, then end session `filter_exhausted`, flagged) -> anti-repetition (3-gram overlap >=0.5 vs last 6 turns, or the same 2-word opener 2x in the last 4; <=2 retries with +0.1 repeat penalty and a "vary phrasing and topic" note) -> atomic ended-check -> persist reply with tags.

**Debrief** (`backend/debrief.py`): all percentages and scalars computed in code from logged tags. The same served model only paraphrases up to two logged attacker turns per strategy; paraphrases pass the same output filter and fall back to a truncated excerpt. One llama-server is reused (no second model loaded). Percentages are *intended* exposure (stage-derived tags); validity is checked by a researcher hand-coding a sample.
