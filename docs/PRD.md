# PRD: Manipulation-Simulation Training Agent (thesis artefact)

## 1. Purpose
A local chat agent that simulates a persuasive online manipulator so adult participants experience personalised manipulation safely, then learn in a debrief which strategies were used. Replaces an earlier static, awareness-campaign-style version; the new contribution is a personalised, dynamic, director-driven agent.

## 2. Users
- **Participant**: adult (18+), consented, unprimed ("training system that protects against manipulation").
- **Researcher**: configures personas/model, is present or reachable, reviews logs, handles deletion requests.

## 3. Goals / non-goals
Goals: dynamic responsiveness to user text; six-strategy exposure tagging; offender_type and register scalars; safe, fully local operation; grounded debrief.
Non-goals: general-purpose grooming tool; persona authoring UI for participants; any minor persona; explicit sexual content; cloud inference; telemetry.

## 4. Hard requirements (HR)
| ID | Requirement | Enforced by |
|----|-------------|-------------|
| HR1 | Participants 18+ (age gate); personas age >= 19; no minor-related content | config validator at load + output filter |
| HR2 | No explicit sexual content or image solicitation; ceiling = `onset_non_explicit` (ethics-board approved, see ETHICS_NOTES) | output filter + stage gating |
| HR3 | Stop button and text trigger end chat instantly, no persona reply | backend kill endpoint + frontend |
| HR4 | 45-min cap per persona conversation, enforced server-side (sweeper + per-request check). Visible timer removed by researcher decision (D-021) | backend clock |
| HR5 | Fully local, no runtime network, no telemetry | llama-server bound to 127.0.0.1; no external calls |
| HR6 | Pseudonymous IDs, minimal logs, deletion on request | storage layer + delete CLI |
| HR7 | No second LLM watching attacker output | design |
| HR8 | Persona never reveals simulation or lectures during chat | prompt + meta-commentary filter |
| HR9 | Distress/self-harm/real-abuse disclosure interrupts to support screen | rule-based detector |

## 5. Participant flow
Intro (framed study, withdrawal rights) -> consent -> age gate -> participant ID -> persona selection (multiple threads allowed) -> one-to-two sentence context line -> free chat (Stop always visible, no timer shown) -> debrief per conversation + combined summary: strategy cards (name, plain description, % exposure, 1-2 paraphrased examples), offender-type/register summary, helplines, wellbeing check, researcher contact.

## 6. Success metrics
See acceptance criteria (master prompt section 11): offline end-to-end on 16 GB; latency measured; zero ceiling breaches in red-team; repetition below thresholds; gradual adjacent-stage progression; scalar divergence between receptive/resistant profiles; debrief % equals logged tags; Stop/timer/distress tested; helplines current; docs consistent; README-only fresh-clone setup.

## 7. Dependencies / assumptions
- llama.cpp `llama-server` (Vulkan on Windows, CPU fallback), GGUF weights downloaded separately.
- Ethics approval and licence choices come from the researcher (see DECISIONS D-007/D-008).
- Assumption: Ryzen AI 5 340 / 16 GB shared RAM; measured numbers pending (D-002).

## 8. Open questions for the researcher
1. Exact sexualisation ceiling wording (ethics board). 2. LICENSE. 3. Helpline re-verification and max-age threshold (default 90 days). 4. Which participant recruitment/ID scheme. 5. Whether to keep the abliterated-model requirement given code-level safeguards (kept per brief; flagged in ETHICS_NOTES).
