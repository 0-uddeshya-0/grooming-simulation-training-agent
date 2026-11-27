# DECISIONS log
| ID | Decision | Alternatives rejected | Status |
|----|----------|----------------------|--------|
| D-001 | Repo built locally first; GitHub push blocked (GH_TOKEN invalid in build container) | improvising another auth route | open: researcher runs `gh auth login` |
| D-002 | Bake-off harness is shipped (scripts/benchmark); results must be measured on the Ryzen laptop, not here | fabricating/estimating numbers | open |
| D-003 | Stages = the six strategies in taxonomy order; transitions +/-1 only | free strategy choice per turn | proposed |
| D-004 | Model undecided until bake-off; Qwen3-8B abliterated v2 is the *candidate*, not the choice | picking by reputation | open |
| D-005 | Safeguards (age>=19, output filter, distress rules, timer, STOP) are deterministic code; model is untrusted for them | relying on system prompt | accepted |
| D-006 | helplines.yaml last_verified kept as supplied (2025-11-25); it is >1 year old so debrief build fails until re-verified. Intended. | silently bumping the date | accepted |
| D-007 | Sexualisation ceiling encoded as config constant `non_explicit_onset`; exact wording is the ethics board's call | choosing it unilaterally | needs researcher |
| D-008 | LICENSE deferred (needs researcher; third-party model licences noted separately) | defaulting to MIT | needs researcher |
| D-009 | Safety constants hard-coded in backend/constants.py; config can only tighten; config hash logged per session | editable YAML limits | accepted (advisor P0-1) |
| D-010 | Input-side minor handling: user states/implies <18 or contradicts age gate -> deterministic end + support screen; text never enters disclosed_facts | prompt-only deflection | accepted (P0-2) |
| D-011 | Filters: NFKC + zero-width strip + leetspeak/spacing collapse, numeric-age and school-grade patterns, English + German; run on user input, model output and debrief output; fail closed | plain regex | accepted (P0-3) |
| D-012 | S6 not built and allow_onset=false until D-007 resolved | build now, gate later | accepted (P0-4) |
| D-013 | Stop/timer: per-session atomic 'ended' check before persist/deliver; cancel in-flight LLM request and typing delay; monotonic clock + persisted start; 45 min is per participant across threads (proposed, researcher to confirm) | per-thread timer | accepted/needs researcher |
| D-014 | Staleness gate applies to preflight and distress screen, not only debrief; youth line 116 111 to be reviewed for an 18+ study | debrief-only gate | accepted |
| D-015 | Prompt prefix kept stable; director note + summary last (cache reuse); one llama-server reused for debrief (no reload) | reload model for debrief | accepted |
| D-016 | Language: debrief/UI English; filters bilingual EN/DE; participant language confirmed with researcher | English-only filters | needs researcher |
| D-017 | Abliterated vs non-abliterated model: advisor notes persona never needs refusal-free output and S6 + abliterated is highest-risk combination. Brief mandates abliterated; kept, but the bake-off must also include one standard instruct model and the choice is recorded for the ethics board | silently dropping the requirement | needs researcher |
| D-018 | Misuse controls: persona free-text fields length-limited/constrained; localhost bind + researcher session token; repo stays private; access-controlled release only | public repo | accepted |
