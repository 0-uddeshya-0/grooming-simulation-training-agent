"""Safety constants. Hard-coded on purpose (D-009): config may only TIGHTEN, never loosen."""
MIN_PERSONA_AGE = 19
MIN_PARTICIPANT_AGE = 18
MAX_SESSION_SECONDS = 45 * 60          # per persona conversation (D-013)
CONTENT_CEILING = "no_explicit_sexual_content"   # D-007; wording to be confirmed by ethics board
ALLOW_ONSET = False                    # stage 6 not built until ethics wording (D-012)
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
