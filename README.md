# Manipulation-Simulation Training Agent (thesis artefact)

A local, chat-based training agent that simulates a persuasive online manipulator so adult participants experience personalised manipulation in a controlled setting; a debrief then explains which of six strategies they were exposed to (identity manipulation, rapport-building, risk assessment, enticement, relationship-building, sexualisation onset), plus offender-type and register positions. Everything runs on the researcher's laptop: no cloud, no telemetry.

> **Ethics notice.** Adult (18+) participants only. This is a **deception study**: it requires ethics approval, informed consent, a full debrief, and a researcher present or reachable. The persona is always an adult and never produces explicit sexual content (see *Ethics ceiling* below). A Stop button is always visible. **Do not use outside approved research.**

## Requirements
16 GB RAM laptop (tested target: Ryzen AI 5 340 / Radeon 840M), ~8 GB free disk, Python 3.10+, internet **once** for setup (model + llama.cpp). Works offline afterwards.

## Setup and run (three commands)
**Windows (PowerShell)**: PowerShell blocks scripts by default, so run them like this:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
.venv\Scripts\python scripts\download_model.py
powershell -ExecutionPolicy Bypass -File scripts\run.ps1
```
**Linux / macOS**:
```bash
scripts/setup.sh && .venv/bin/python scripts/download_model.py && scripts/run.sh
```
1. **setup** creates `.venv`, installs pinned dependencies and downloads the official llama.cpp build (Vulkan on Windows/Linux) into `bin/`.
2. **download_model** fetches the abliterated GGUF configured in `config/app.yaml` (default: Huihui-Qwen3-8B-abliterated-v2, Q4_K_M), shows the licence from the model card, asks you to confirm you read it, verifies the checksum and writes `models/MODEL_INFO.txt`. If the repo name has changed on Hugging Face: `python scripts/download_model.py --search "Huihui Qwen3 8B abliterated GGUF"`, then set `model.gguf_repo`.
3. **run** checks everything (RAM, model, binary, helplines age, contact details), starts the model server, waits until it is ready, starts the app and opens http://localhost:8000. If the GPU/Vulkan start fails, add `--cpu` to the run command.

Then measure the model on your laptop (not yet done, see `docs/MODEL_BAKEOFF.md`): with the model server running (the run script starts it), in another terminal: `.venv\Scripts\python scripts\benchmark.py --label "Qwen3-8B-abliterated Q4_K_M"` (Linux/macOS: `.venv/bin/python ...`).

## Running a session
Give the participant an ID (e.g. `P001`), open the app, they consent and confirm 18+, pick a persona, chat. **Stop** (or typing `STOP`) ends a chat at once and shows the debrief. Each persona conversation can last up to 45 minutes (enforced by the server; no timer on screen). One researcher must be present or reachable.

**Researcher log viewer** (separate terminal; never shown to participants): `powershell -ExecutionPolicy Bypass -File scripts\researcher.ps1` (or `scripts/researcher.sh`) prints a private URL with a one-time token. It lists sessions, transcripts with the intended strategy tag per attacker message, blocked outputs and distress events, a tag-validity check (mark whether each tag matches the text), CSV export, and per-participant deletion.

## Data and deletion
`data/study.db` (SQLite, git-ignored, pseudonymous IDs only, no WAL files). Participants are told to email the researcher with their ID to have data deleted: use the viewer's delete button or `.venv\Scripts\python scripts\delete_participant.py P001`. Delete everything: remove `data/`. Use full-disk encryption on the laptop.

## Ethics ceiling (approved by the ethics board)
Permitted ("onset"): friendly compliments about personality or humour; mildly flirtatious or romantic language of the kind on mainstream messaging/dating apps; non-explicit questions about relationship status and feelings; steering from general to personal/emotional topics.
Prohibited at all times: sexual acts, anatomy or explicit language; sexual role-play; requesting/offering sexual or nude images or video; minors or youthfulness in a sexual/romantic context; threats, blackmail or pressure; asking for money, address, workplace, full name or other identifying data; proposing in-person meetings; encouraging self-harm. If the participant raises such content, the persona does not mirror it.
Enforced in code (`backend/filters.py`, switch `CEILING_ENFORCED` is on), not just in the prompt: an output filter blocks and logs violations before the participant sees them; personas are validated at startup; automated red-team tests run in CI. The model is treated as untrusted.

## Safeguards (summary, see docs/SECURITY.md)
Stop button + whole-message `STOP`; server-side 45-min clock with sweeper; age gate and adult-only personas (19+); output filter; user-under-18 and distress rules end the chat and show support; helplines with a verification date (app refuses to run if older than 60 days); everything local.

## Before the first participant
- Re-verify every helpline in `config/helplines.yaml` and update `last_verified` (the TelefonSeelsorge note still says "(confirm)").
- Run the bake-off and record the chosen model in `docs/DECISIONS.md`.
- Check `config/app.yaml` `study:` details; test one full session yourself; keep a researcher present.

## Tests
`python -m pytest -q` (no model needed; the LLM is mocked / a fake llama-server is used). CI runs them on every push. Browser tests: `tests/ui/README.md`.

## Docs
`docs/`: PRD, ARCHITECTURE, STATE_MACHINE, LLM_ORCHESTRATION, PERSONA_PROMPT, API_SPEC, SECURITY, ETHICS_NOTES, UX_DESIGN, DECISIONS, SCHEMA.sql, MODEL_BAKEOFF (after benchmarking).

## Licence
MIT for this code. Model weights (Qwen, Llama, Gemma derivatives) and llama.cpp carry their own licences; see `models/MODEL_INFO.txt` and `bin/llama/LLAMA_INFO.txt` after setup.
