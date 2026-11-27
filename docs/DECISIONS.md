# DECISIONS log
| ID | Decision | Alternatives rejected | Status |
|----|----------|----------------------|--------|
| D-001 | Repo built locally first; GitHub push blocked (GH_TOKEN invalid in build container) | improvising another auth route | open: researcher runs `gh auth login` |
| D-002 | Bake-off harness is shipped (scripts/benchmark); results must be measured on the Ryzen laptop, not here | fabricating/estimating numbers | open |
| D-003 | Stages = the six strategies in taxonomy order; transitions +/-1 only | free strategy choice per turn | proposed |
| D-004 | Model undecided until bake-off; Qwen3-8B abliterated v2 is the *candidate*, not the choice | picking by reputation | open |
| D-005 | Safeguards (age>=19, output filter, distress rules, timer, STOP) are deterministic code; model is untrusted for them | relying on system prompt | accepted |
| D-006 | helplines.yaml last_verified kept as supplied (2025-11-25); it is >1 year old so debrief build fails until re-verified. Intended. | silently bumping the date | accepted |
| D-007 | Ceiling (supervisors + ethics board): no explicit sexual content; never graphic sexual text, sexual images, or solicitation of images. Encoded as constant `CONTENT_CEILING`; exact wording still to be confirmed in writing by the board | - | accepted |
| D-008 | MIT licence (researcher decision); third-party model licences noted separately | - | accepted |
| D-009 | Safety constants hard-coded in backend/constants.py; config can only tighten; config hash logged per session | editable YAML limits | accepted (advisor P0-1) |
| D-010 | Input-side minor handling: user states/implies <18 or contradicts age gate -> deterministic end + support screen; text never enters disclosed_facts | prompt-only deflection | accepted (P0-2) |
| D-011 | Filters: NFKC + zero-width strip + leetspeak/spacing collapse, numeric-age and school-grade patterns, English + German; run on user input, model output and debrief output; fail closed | plain regex | accepted (P0-3) |
| D-012 | S6 not built and allow_onset=false until D-007 resolved | build now, gate later | accepted (P0-4) |
| D-013 | Stop/timer: per-session atomic 'ended' check before persist/deliver; cancel in-flight LLM request and typing delay; monotonic clock + persisted start; 45 min applies per persona conversation (researcher decision: each persona thread gets its own 45 min; no participant-wide timer) | participant-wide timer | accepted |
| D-014 | Helplines added only after verification; staleness gate applies to preflight and distress screen, not only debrief; youth line 116 111 to be reviewed for an 18+ study | debrief-only gate | accepted |
| D-015 | Prompt prefix kept stable; director note + summary last (cache reuse); one llama-server reused for debrief (no reload) | reload model for debrief | accepted |
| D-016 | English only (researcher decision). Filters EN only; audit's German patterns dropped | bilingual | accepted |
| D-017 | Abliterated model required (researcher decision: persona must behave like a real attacker with no model refusals; limits enforced by code). No standard-model comparison added | non-abliterated model | accepted |
| D-018 | Misuse controls: persona free-text fields length-limited/constrained; localhost bind + researcher session token; repo stays private; access-controlled release only | public repo | accepted |
| D-019 | UI restyled in shadcn/ui design language (zinc tokens) in plain CSS; no React/Node build, to keep the no-Node run requirement. impeccable.style and a shadcn plugin were not reachable/available from the build container, so critique was done manually plus the built-in design skills | adopting React + shadcn | accepted |
| D-021 | Visible timer removed from the UI (researcher decision: conversation should feel natural). Limit still enforced server-side; deviation from master prompt HR4 'visible timer' flagged to ethics board | visible timer | accepted |
| D-022 | Claymorphism laptop-first UI: sidebar of conversations + pane; plain CSS/JS, no build step; see UX_DESIGN.md. Two more adult personas (Sam 27, Jordan 31) added so multi-thread is real | single-thread phone-style UI | accepted |
| D-023 | Bug found by browser test: idle sessions never ended. Fixed with sweeper + enforce_time on status | lazy check only on message | fixed |
| D-020 | Model-server outage returns 503 and keeps the session open; UI shows a friendly message and Stop still works. Distress/under-18 endings show the support card first | silent 500 | accepted |
| D-024 | Ethics-board ceiling adopted (onset level; prohibited list incl. money, identifying data, meetings, pressure, self-harm). Encoded in filters + `CEILING_ENFORCED` constant; stage 6 built with extra gating (>=18 turns, engagement, disclosures, 25% share cap) after a test showed short "sure/cool" replies could reach onset | keep S6 unbuilt | accepted (supersedes D-012) |
| D-025 | Study/helpline config adopted verbatim from researcher; helplines `max_age_days: 60` lives in helplines.yaml; supervisor angle brackets stripped | app.yaml-only threshold | accepted |
| D-026 | Participant-facing DELETE endpoint removed; deletion by email to researcher -> viewer button or `scripts/delete_participant.py` | open localhost delete | accepted |
| D-027 | Researcher log viewer: separate app/port/token, UI outside frontend/, tag-validity review table, CSV export, deletion | route inside participant app | accepted |
| D-028 | One-command launcher (`scripts/launch.py`) waits for model health, `--cpu` fallback, `<think>` stripping, `--jinja` for chat_template_kwargs | separate shell scripts per OS | accepted |
| D-029 | Model repo `mradermacher/Huihui-Qwen3-8B-abliterated-v2-GGUF` is UNVERIFIED (no HF access when written); download script reads the HF API, picks the quant, verifies sha256 and offers `--search` | hard-coding a filename | open until first download |
| D-030 | Higher-tier (Opus-class) advisor review applied: English-only guard, filter gap/false-positive fixes, 'register' expressed as taking the lead never pressure, flirt leaning only from stage 5, raw user text removed from prompts, resistance/disclosure scoring fixed, onset gates tuned (14 turns, EMA>=4.5 words, 2 disclosures; reached by most engaged users in simulation), neutral fallback lines, async stop/status, busy guard, UTF-8 I/O, pinned model file in config_hash, resumable download, port check, Windows ExecutionPolicy instructions | ignore | accepted |
