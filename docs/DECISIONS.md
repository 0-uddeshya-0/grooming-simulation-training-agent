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
