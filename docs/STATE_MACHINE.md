# STATE_MACHINE (director)

Inspired by StagePilot (prompt-only simulators stall early and loop; reviewers found progression too fast/linear, hence pacing + regression + randomness). All of this is code, not a model.

## Stages (= taxonomy order)
S1 Identity manipulation -> S2 Rapport-building (victim assessment) -> S3 Risk assessment -> S4 Enticement -> S5 Relationship-building -> S6 Sexualisation onset (non-explicit, gated).

## State per session
turn_idx, stage, turns_in_stage, intent_history[(primary, secondary)], offender_type in [0,1], register in [0,1], disclosed_facts (rolling summary), last_openers (N=6), receptiveness EMA in [0,1], resistance_streak, flags.

## User signal scoring (rules, per user message)
disclosure (personal facts, feelings, names, location words), warmth (positive affect, emojis, thanks, questions back), resistance (refusal, "no", "stop talking about", suspicion, "why do you ask"), topic_change, shortness (<=3 words). Each yields a value in [0,1]; receptiveness = EMA(0.5*warmth + 0.4*disclosure - 0.6*resistance - 0.1*shortness, alpha 0.4), clipped.

## Transition rules
- Only stay, advance (+1) or regress (-1). Never jump.
- Min dwell per stage: S1 3, S2 4, S3 3, S4 3, S5 4 turns (config). S6 requires: turns_total >= 18, receptiveness >= 0.6, resistance_streak == 0, content ceiling permits, researcher flag `allow_onset` true.
- Advance when dwell met AND receptiveness >= threshold(stage) (0.35 -> 0.6 rising per stage) AND random draw p=0.6 (stochastic pacing).
- Regress when resistance_streak >= 2 or receptiveness < 0.2; also sets a 2-turn cooldown (no advance).
- A hard resistance signal (explicit refusal) forces secondary intent to "ease off/soft rapport" for 1-2 turns and lowers register passivity bias accordingly (see below).
- S6 is dropped (back to S5) immediately on any resistance; S6 exposure is capped at a config share of turns (default 25%).

## Scalars (bounded steps)
offender_type: step +/-0.05 per turn max. Rises with receptiveness while at S4+ (sexual-preoccupation lean when user is receptive to flirt-type topics); falls toward intimacy-seeking when user discloses emotional needs. Clipped [0,1], starts at persona bias.
register: step +/-0.05. Resistance increases control (pushiness); receptive user lets it relax (passive). Neither scalar is a stage; both only modify the director note's expression hints.

## Tagging
Each attacker turn logs primary tag = stage's strategy, optional secondary (e.g. S3 turn also rapport). Exposure % per strategy = tagged turns / total attacker turns (primary and secondary counted, reported separately).

## Terminal states
Stop button/"STOP", 45-min timer, distress interrupt, repeated filter hits -> session ends, no persona message, debrief. All logged with reason.

## Test obligations
Receptive/neutral/resistant scripted users: assert adjacent-only transitions, min dwell respected, regression under resistance, scalar divergence, S6 never reached for resistant profile.
