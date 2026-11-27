# UX_DESIGN (UI design system, flows, usability)
**Principles**: look like an ordinary messaging app so participants behave naturally; stay unprimed (no warnings, no timer, no study vocabulary in the chat); keep Stop obvious; make the debrief clear and kind.

**Layout (laptop-first, 1280x720 and up)**: two panes. Left: conversation list (avatar, name and age, last-message preview, typing / unread / "Debrief" state) and an "Overall summary" button. Right: chat, debrief or summary. Under 900 px the list becomes a horizontal strip.

**Visual language (claymorphism, restrained)**: warm sand surfaces, soft paired light/dark shadows with inner highlights, 20-28 px radii, one teal accent (chat bubbles, meters), coral only for Stop and support. No gradients, glow, emoji icons or decorative illustration. System font stack (no runtime font downloads). Body 15 px, contrast >= 4.5:1, targets >= 40 px, visible focus ring, `prefers-reduced-motion` respected.

**Flow**: consent + 18+ -> participant ID -> pick a person -> free chat -> Stop (or STOP text, distress/under-18 rule, server time limit) -> debrief for that chat -> optionally more chats -> overall summary.

**Chat details that make it feel real**: grouped bubbles, time stamps, "Seen" then a typing indicator before each reply, reply delay scaled to message length (minus the model's own latency), occasional two-part replies, per-thread drafts kept when switching, unread dot for replies that arrive in another thread, "New message" chip when scrolled up, Enter sends / Shift+Enter newline, composer grows to 5 lines.

**No visible timer (D-021)**: the 45-minute limit is enforced by the server (sweeper plus checks on every request). The UI polls quietly and moves to the debrief when time is up. Flag for the ethics board: participants are not shown the limit; the information sheet should state the maximum duration.

**Debrief**: strategy cards with a percentage meter and one or two paraphrased examples from the chat; a stage-over-time chart; offender-type and register gauges with plain-language captions; a three-option wellbeing check (nothing recorded); helplines; researcher contact. After a distress or under-18 ending the support card comes first, with a gentle heading. Overall summary pools all finished chats.

**Usability checks**: keyboard-only use (skip link, labelled controls, `role=log` with `aria-live=polite`, thread buttons with `aria-current`); error states in plain language (model server down: reply-less note, Stop still works); no layout shift while typing indicator appears.
