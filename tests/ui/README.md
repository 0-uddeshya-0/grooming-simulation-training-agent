# Browser smoke tests (Playwright, mock LLM; not part of CI)
```bash
python tests/ui/launch_mock.py &                 # port 8123, mock model, temp DB, temp helplines
node tests/ui/smoke.js ./shots                   # consent, 3 threads, unread dot, Stop, STOP text, distress, summary
LIMIT_MIN=1 PORT=8124 python tests/ui/launch_mock.py &
node tests/ui/idle_timeout.js                    # idle session ends server-side (~60 s), no visible timer
```
Requires `npm i playwright` (dev only; the app itself needs no Node).
