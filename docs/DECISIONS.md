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
| D-020 | Model-server outage returns 503 and keeps the session open; UI shows a friendly message and Stop still works. Distress/under-18 endings show the support card first | silent 500 | accepted |
