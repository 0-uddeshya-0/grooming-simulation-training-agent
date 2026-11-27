# Manipulation-Simulation Training Agent (thesis artefact)

**STATUS: backend, UI and tests working with a mocked LLM. Real-model bake-off and ethics wording pending.** See `docs/DECISIONS.md`.

## Ethics notice
Adult (18+) participants only. This is a **deception study**: it requires ethics approval, informed consent, a full debrief, and a researcher present or reachable. The simulation never depicts minors and never produces explicit sexual content. A Stop button is always visible and ends the chat immediately. Sessions are capped at 45 minutes.
**Do not use outside approved research.**

## Hardware
Target: 16 GB RAM laptop (Ryzen AI 5 340, Radeon 840M iGPU). Needs Python 3.10+ and a llama.cpp `llama-server` binary (Vulkan build on Windows).

## Setup (three commands)
```bash
scripts/setup.sh                                  # Windows: scripts\setup.ps1
.venv/bin/python scripts/download_model.py        # after setting model.gguf_repo/gguf_file in config/app.yaml
scripts/run.sh                                    # Windows: scripts\run.ps1
```
Before any participant: (1) re-verify every number in `config/helplines.yaml` and update `last_verified` (the app refuses to start if older than 90 days); (2) set `study.researcher_contact` in `config/app.yaml`; (3) choose the model with `python scripts/benchmark.py --label "<model quant>"` (writes `docs/MODEL_BAKEOFF.md`) and record the decision in `docs/DECISIONS.md`.

## Test session
Run `scripts/run.sh`, open http://localhost:8000, use a pseudonymous ID such as `T001`. Try Stop, wait for the timer, and open the debrief.
Tests (no model needed): `.venv/bin/python -m pytest -q`. For a UI try-out without a model: `SIM_MOCK_LLM=1` (fixed replies).

## Data
`data/study.db` (git-ignored). Delete one participant: `curl -X DELETE http://localhost:8000/api/participant/T001`. Delete everything: remove `data/`.

## Safeguards (summary, see docs/SECURITY.md)
Always-visible Stop and a whole-message "STOP"; 45 min per persona conversation, enforced server-side; adults only (age gate, personas 19+); code-level output filter (no minors, no explicit content, no image requests, no meta commentary); user-minor and distress rules end the chat and show support; everything local.

## Docs
`docs/` PRD, ARCHITECTURE, STATE_MACHINE, LLM_ORCHESTRATION, API_SPEC, SECURITY, ETHICS_NOTES, DECISIONS, SCHEMA.sql, PERSONA_PROMPT.
Model weights are third-party and carry their own licences (see `models/MODEL_INFO.txt` after download).
