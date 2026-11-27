"""Safety constants. Hard-coded on purpose (D-009): config may only TIGHTEN, never loosen."""
MIN_PERSONA_AGE = 19
MIN_PARTICIPANT_AGE = 18
MAX_SESSION_SECONDS = 45 * 60          # per persona conversation (D-013)
# Ethics board approved ceiling (D-007, D-024): "onset" level only. Permitted: compliments on personality/humour, mildly
# flirtatious/romantic language of mainstream apps, non-explicit questions about relationship status and feelings,
# steering toward personal/emotional topics. Prohibited always: see backend/filters.py (explicit sexual content/anatomy,
# sexual role-play, image/video requests, minors/youthfulness in romantic context, threats/blackmail/pressure,
# money, identifying data, in-person meetings, self-harm encouragement).
CONTENT_CEILING = "onset_non_explicit"
CEILING_ENFORCED = True                # switch is ON; filters always run (tests assert this)
ALLOW_ONSET = True                     # stage 6 (onset) available; config may only turn it off, never on
STOP_TRIGGERS = ("stop",)              # whole-message, case-insensitive
MAX_FILTER_REGENERATIONS = 3
MAX_ANTIREPEAT_RETRIES = 2
MAX_LIMIT_PUSHES = 3                   # user pushes past limits before session ends

STRATEGIES = (
    "Identity manipulation",
    "Rapport-building (victim assessment)",
    "Risk assessment",
    "Enticement",
    "Relationship-building",
    "Sexualisation (onset)",
)
