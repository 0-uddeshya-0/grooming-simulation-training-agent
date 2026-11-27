# API_SPEC (127.0.0.1 only)
| Method | Path | Body | Result |
|---|---|---|---|
| GET | /api/personas | - | `[{id,name,context_line}]` (no prompts exposed) |
| POST | /api/session | `{participant_id, persona_id, consent, age_confirmed}` | `{sid, context_line, limit_seconds}`; 403 without consent + 18+ |
| GET | /api/session/{sid} | - | `{ended, reason, remaining}` |
| POST | /api/session/{sid}/message | `{text}` | `{ended:false, messages:[{text,delay_ms}], remaining}` or `{ended:true, reason, support}` |
| POST | /api/session/{sid}/stop | - | `{ended:true, reason:"stop"}`; instant, never calls the LLM; cancels in-flight generation |
| GET | /api/session/{sid}/debrief | - | cards, scalar summaries, helplines, contact; 409 while running; 503 if helplines stale |
| DELETE | /api/participant/{pid} | - | `{deleted_sessions}`; removes all rows and VACUUMs |
End reasons: `stop | timeout | distress | user_minor | limit_pushes | filter_exhausted`. `support:true` (distress, user_minor) tells the UI to show the support message first.
