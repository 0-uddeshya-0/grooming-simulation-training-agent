# ARCHITECTURE

```
Browser UI (chat, Stop) <-> FastAPI (127.0.0.1) <-> model: Hyperbolic cloud API (HTTPS, default) | llama-server (GGUF, 127.0.0.1:8081)
                                      |
                       SQLite (data/*.db, git-ignored)
                                      |
        Director/State machine -> Deterministic safeguards -> Debrief generator
```
- **Frontend**: static prebuilt files (index.html, styles.css, app.js), no Node needed. Sidebar of conversations + chat/debrief/summary pane, typing indicator, delay proportional to message length, always-visible Stop, no timer shown; quiet status polling detects server-side time-outs. See UX_DESIGN.md.
- **Backend (FastAPI)**: sessions, turn pipeline, server-side 45-min clock (background sweeper ends idle sessions), kill-switch endpoint, config validation at startup, preflight checks (RAM, model, binary, helplines age).
- **Turn pipeline**: user text -> stop/distress rules -> signal scoring -> director update -> prompt assembly -> LLM -> output filter (regenerate on hit; end after N) -> anti-repetition n-gram check (<=2 retries) -> persist (turn + tags + state snapshot) -> deliver with simulated delay.
- **Safeguards module**: pure functions, no model calls; unit-tested; the actual guarantee for HR1/HR2/HR9.
- **Debrief**: after the session, reads structured logs; computes percentages in code; the LLM (same GGUF, different prompt, loaded after chat ends; never two models at once) only phrases explanations and paraphrases examples from logged turns. Build fails if helplines are stale.
- **Model-agnostic**: model, quant, sampling, template switches in `config/app.yaml`.
- **Privacy**: no outbound network, pseudonymous IDs, `DELETE /api/participant/{pid}` removes all rows. No raw attacker prompts exported; personas live in researcher-side `config/`.
- **Mocking**: LLM client interface has a mock implementation so CI runs without weights.
- **Researcher viewer** (`backend/researcher.py`, port 8001, token): read-mostly view of the same SQLite DB (sessions, transcripts with intended tags, blocked outputs, distress events, tag-validity review, CSV export, deletion). Separate from the participant app.
- **Launcher** (`scripts/launch.py`): preflight -> llama-server (`--jinja`, GPU layers from config, `--cpu` fallback) -> wait for `/health` -> app -> browser.
