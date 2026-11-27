# API_SPEC (127.0.0.1 only)
| Method | Path | Body | Result |
|---|---|---|---|
| GET | /api/personas | - | `[{id,name,age,context_line}]` (no prompts exposed) |
| POST | /api/session | `{participant_id, persona_id, consent, age_confirmed}` | `{sid, context_line, limit_seconds}`; 403 without consent + 18+ |
| GET | /api/session/{sid} | - | `{ended, reason, remaining}`; also enforces the time limit (idle sessions end here or via the sweeper) |
| POST | /api/session/{sid}/message | `{text}` | `{ended:false, messages:[{text,delay_ms}], remaining}` or `{ended:true, reason, support}` |
| POST | /api/session/{sid}/stop | - | `{ended:true, reason:"stop"}`; instant, never calls the LLM; cancels in-flight generation |
| GET | /api/session/{sid}/debrief | - | cards, `stages[]`, `offender_value`/`register_value` (0-1) and text summaries, helplines, contact; 409 while running; 503 if helplines stale |
| GET | /api/participant/{pid}/summary | - | pooled exposure across finished chats, per-chat scalars, helplines; 409 if none finished |
| GET | /api/study | - | `{title, researcher_name, researcher_contact, max_session_minutes}` |
| GET | /api/health | - | `{model_ready}` (llama-server reachable) |
End reasons: `stop | timeout | distress | user_minor | limit_pushes | filter_exhausted`. `support:true` (distress, user_minor) tells the UI to show the support message first.

## Researcher API (separate app, port 8001, token via cookie or `X-Researcher-Token`)
`GET /` (UI; `?token=` sets cookie) · `GET /api/r/sessions` · `GET /api/r/session/{sid}` (turns with intended tags, events incl. blocked text, snapshots, exposure, review stats) · `POST /api/r/review {sid, idx, agree}` · `GET /api/r/export.csv` · `DELETE /api/r/participant/{pid}`.
The participant app has no deletion endpoint.
