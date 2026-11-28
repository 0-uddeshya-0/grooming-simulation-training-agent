"use strict";
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const hue = id => [...id].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const clock = t => new Date(t).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
const SUPPORT_REASONS = ["distress", "user_minor"];
const ICON_SEND = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3.4 20.4 21 12 3.4 3.6l-.1 6.5L15 12 3.3 13.9z"/></svg>';
const ICON_STOP = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="2" width="12" height="12" rx="2.5"/></svg>';

const A = {pid: "", personas: [], threads: new Map(), view: "welcome", poll: null};

const post = (url, body) => fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
const avatar = (p, lg) => `<span class="avatar${lg ? " lg" : ""}" style="--h:${hue(p.id)}" aria-hidden="true">${esc(p.name[0])}</span>`;

/* ================= gate ================= */
fetch("/api/study").then(r => r.json()).then(s => { $("title").textContent = s.title; $("maxmin").textContent = s.max_session_minutes;
  $("rname").textContent = s.researcher_name + ", " + s.researcher_contact; document.title = s.title;
  if (s.model_location === "remote") $("privacy").textContent = `The study runs on this computer, but your messages are sent to an external AI service (${s.model_provider}) so that it can write the replies. Nothing else about you is shared, and you are only identified by your participant ID.`; }).catch(() => {});
$("next1").onclick = () => {
  if (!$("c1").checked || !$("c2").checked) { $("err1").textContent = "Please tick both boxes to continue."; return; }
  $("err1").textContent = ""; $("g1").hidden = true; $("g2").hidden = false; $("st2").classList.add("on"); $("pid").focus();
};
$("back1").onclick = () => { $("g2").hidden = true; $("g1").hidden = false; $("st2").classList.remove("on"); };
$("pid").onkeydown = e => { if (e.key === "Enter") $("go").click(); };
$("go").onclick = async () => {
  const pid = $("pid").value.trim();
  if (!/^[\w.-]{1,40}$/.test(pid)) { $("err").textContent = "Enter the ID the researcher gave you (letters, numbers, - . _)."; return; }
  A.pid = pid;
  try { const h = await (await fetch("/api/health")).json(); if (!h.model_ready) { $("err").textContent = "The chat model is still loading. Please wait a moment and try again."; return; } } catch {}
  try { A.personas = await (await fetch("/api/personas")).json(); }
  catch { $("err").textContent = "Cannot reach the study server. Tell the researcher."; return; }
  A.personas.forEach(p => A.threads.set(p.id, {p, sid: null, state: "idle", msgs: [], busy: false, typing: false, seen: false,
    unread: 0, support: false, debrief: null, draft: ""}));
  $("gate").hidden = true; $("stage").hidden = false; $("pidchip").textContent = "ID " + pid;
  paintSide(); setView("welcome");
};

/* ================= sidebar ================= */
function paintSide() {
  $("threads").innerHTML = "";
  for (const th of A.threads.values()) {
    const b = document.createElement("button");
    b.className = "thread"; b.setAttribute("aria-current", String(A.view === th.p.id));
    const last = th.msgs[th.msgs.length - 1];
    const pv = th.state === "ended" ? "Debrief ready" : th.typing ? "typing…" : last ? (last.from === "me" ? "You: " : "") + last.text : "Start a conversation";
    const right = th.state === "ended" ? '<span class="tag">Debrief</span>' : th.unread ? '<span class="dot" aria-label="unread"></span>' : "";
    b.innerHTML = `${avatar(th.p)}<span class="tx"><b>${esc(th.p.name)}, ${th.p.age}</b><span class="pv">${esc(pv)}</span></span>${right}`;
    b.onclick = () => openThread(th.p.id);
    $("threads").appendChild(b);
  }
  $("sumbtn").disabled = ![...A.threads.values()].some(t => t.state === "ended");
}
$("sumbtn").onclick = () => setView("summary");

/* ================= views ================= */
function setView(v) {
  A.view = v; const pane = $("pane");
  if (v === "welcome") {
    pane.innerHTML = `<div class="welcome"><h2>Pick someone to talk to</h2><p class="muted">Choose a conversation on the left. You can talk to more than one person, each in their own chat. Press <b>Stop</b> whenever you want to end a chat.</p></div>`;
  } else if (v === "summary") { paintSummary(); }
  else {
    const th = A.threads.get(v);
    if (th.state === "ended") paintDebrief(th); else paintChat(th);
  }
  paintSide();
}

async function openThread(id) {
  const th = A.threads.get(id);
  if (th.state === "idle") {
    try {
      const r = await post("/api/session", {participant_id: A.pid, persona_id: id, consent: true, age_confirmed: true});
      if (!r.ok) throw 0;
      const s = await r.json(); th.sid = s.sid; th.ctx = s.context_line; th.state = "live";
      ensurePoll();
    } catch { A.view = id; $("pane").innerHTML = `<div class="welcome"><h2>Could not start</h2><p class="muted">Please tell the researcher.</p></div>`; paintSide(); return; }
  }
  th.unread = 0; setView(id);
}

/* ================= chat ================= */
function paintChat(th) {
  $("pane").innerHTML = `<div class="view">
    <div class="head">${avatar(th.p, true)}<div class="nm"><h3>${esc(th.p.name)}</h3><small><span class="presence"></span>Online</small></div>
      <button class="btn stop" id="stop" aria-label="Stop and end this chat">${ICON_STOP}Stop</button></div>
    <div id="log" role="log" aria-live="polite" aria-label="Conversation with ${esc(th.p.name)}"></div>
    <form id="composer"><textarea class="field" id="inp" rows="1" placeholder="Write a message…" aria-label="Message"></textarea>
      <button class="btn primary" id="send" type="submit" aria-label="Send" disabled>${ICON_SEND}</button></form></div>`;
  const inp = $("inp"); inp.value = th.draft;
  const fit = () => { inp.style.height = "auto"; inp.style.height = Math.min(inp.scrollHeight, 140) + "px"; $("send").disabled = !inp.value.trim() || th.busy; th.draft = inp.value; };
  inp.oninput = fit;
  inp.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("composer").requestSubmit(); } };
  $("composer").onsubmit = e => { e.preventDefault(); send(th); };
  $("stop").onclick = () => stop(th);
  th.fit = fit; fit(); paintLog(th, true); inp.focus();
}

function paintLog(th, force) {
  const log = $("log"); if (!log || A.view !== th.p.id) return;
  const near = log.scrollHeight - log.scrollTop - log.clientHeight < 90;
  let h = `<div class="ctx">${esc(th.ctx)}</div>`;
  if (th.msgs.length) h += `<div class="sep">Today ${clock(th.msgs[0].ts)}</div>`;
  const lastMeIdx = th.msgs.map(m => m.from).lastIndexOf("me");
  th.msgs.forEach((m, i) => {
    const prev = th.msgs[i - 1], next = th.msgs[i + 1];
    h += `<div class="row ${m.from}${prev && prev.from !== m.from ? " gap" : ""} ${m.from === "me" ? "me" : "them"}"><div class="bubble">${esc(m.text)}</div></div>`;
    if (!next || next.from !== m.from) h += `<div class="meta${m.from === "me" ? " r" : ""}">${clock(m.ts)}${m.from === "me" && i === lastMeIdx && th.seen && i === th.msgs.length - 1 ? " · Seen" : ""}${m.from === "me" && i === lastMeIdx && th.seen && i !== th.msgs.length - 1 ? "" : ""}</div>`;
  });
  if (th.note) h += `<div class="note" role="status">${esc(th.note)}</div>`;
  if (th.paused) h += `<div class="card support" id="pausecard"><h3>Let's pause for a moment</h3><p>${esc(th.supportData?.wellbeing_note || "If anything feels too much, please talk to the researcher or a support line.")}</p>${th.supportData?.helplines ? lines(th.supportData) : ""}<p><button class="btn primary" id="pc-go" type="button">Continue the chat</button> <button class="btn" id="pc-end" type="button">End chat and see debrief</button></p></div>`;
  if (th.typing) h += `<div class="row them gap"><div class="bubble typing" aria-label="${esc(th.p.name)} is typing"><i></i><i></i><i></i></div></div>`;
  log.innerHTML = h;
  if (th.paused) { $("pc-go").onclick = () => { th.paused = false; paintLog(th, true); $("inp").focus(); }; $("pc-end").onclick = () => stop(th); }
  if (near || force) log.scrollTop = log.scrollHeight;
  else if (th.newBelow) log.insertAdjacentHTML("beforeend", '<button class="btn" id="jump" type="button">New message ↓</button>'), $("jump").onclick = () => { log.scrollTop = log.scrollHeight; th.newBelow = false; $("jump").remove(); };
}

async function send(th) {
  const text = th.draft.trim(); if (!text || th.busy || th.state !== "live") return;
  th.busy = true; th.note = ""; th.seen = false; th.paused = false; th.msgs.push({from: "me", text, ts: Date.now()}); th.draft = "";
  $("inp").value = ""; th.fit(); paintLog(th, true); paintSide();
  const t0 = Date.now();
  const tSeen = setTimeout(() => { if (th.busy) { th.seen = true; paintLog(th); } }, 700 + Math.random() * 700);
  const tType = setTimeout(() => { if (th.busy) { th.typing = true; paintLog(th, true); paintSide(); } }, 1500 + Math.random() * 600);
  let r;
  try { const res = await post(`/api/session/${th.sid}/message`, {text}); if (!res.ok) throw 0; r = await res.json(); }
  catch {
    clearTimeout(tSeen); clearTimeout(tType); th.busy = false; th.typing = false;
    th.note = "No reply: the chat service is not responding. Tell the researcher, or try again.";
    paintLog(th, true); paintSide(); if (A.view === th.p.id) th.fit(); return;
  }
  clearTimeout(tSeen); clearTimeout(tType);
  if (r.ended) { th.busy = false; th.typing = false; return handleEnd(th, r.reason, r.support); }
  if (r.paused) {                                    // distress words: gentle pause with support, participant decides
    th.busy = false; th.typing = false; th.seen = false; th.paused = true;
    try { th.supportData = await (await fetch("/api/support")).json(); } catch { th.supportData = null; }
    paintLog(th, true); paintSide(); if (A.view === th.p.id) { th.fit(); } return;
  }
  th.seen = true;
  for (let i = 0; i < r.messages.length; i++) {
    const m = r.messages[i], wait = Math.max(i ? m.delay_ms : 350, (i ? m.delay_ms : m.delay_ms - (Date.now() - t0)));
    th.typing = true; paintLog(th, true); paintSide();
    await sleep(wait);
    if (th.state !== "live") return;
    th.typing = false; th.msgs.push({from: "them", text: m.text, ts: Date.now()});
    if (A.view === th.p.id) { th.newBelow = true; paintLog(th); th.newBelow = false; } else th.unread++;
    paintSide();
  }
  th.busy = false; paintSide();
  if (A.view === th.p.id) { th.fit(); $("inp").focus(); }
}

async function stop(th) {
  if (th.state !== "live") return;
  try { await post(`/api/session/${th.sid}/stop`); } catch {}
  handleEnd(th, "stop", false);
}

/* ================= end of conversation ================= */
async function handleEnd(th, reason, support) {
  if (th.state === "ended") return;
  th.state = "ended"; th.busy = false; th.typing = false; th.reason = reason; th.support = !!support;
  try { const r = await fetch(`/api/session/${th.sid}/debrief`); th.debrief = await r.json(); th.debriefOk = r.ok; }
  catch { th.debrief = {detail: "server not reachable"}; th.debriefOk = false; }
  if (A.view === th.p.id) setView(th.p.id); else paintSide();
  if (![...A.threads.values()].some(t => t.state === "live")) { clearInterval(A.poll); A.poll = null; }
}

function ensurePoll() {   // no visible timer: quietly notice server-side time-outs
  if (A.poll) return;
  A.poll = setInterval(async () => {
    for (const th of A.threads.values()) {
      if (th.state !== "live") continue;
      try { const s = await (await fetch(`/api/session/${th.sid}`)).json(); if (s.ended) handleEnd(th, s.reason, SUPPORT_REASONS.includes(s.reason)); } catch {}
    }
  }, 6000);
}

/* ================= debrief ================= */
const lines = d => `<ul class="lines">${d.helplines.map(l => `<li><b>${esc(l.name)}</b><br>${esc(l.number)}${l.hours ? ` <span class="small muted">· ${esc(l.hours)}</span>` : ""}${l.note ? `<br><span class="small muted">${esc(l.note)}</span>` : ""}</li>`).join("")}</ul><p class="small muted">Helplines last verified ${esc(d.helplines_last_verified)}</p>`;
const contact = d => { const r = d.researcher; return `<div class="card"><h3>Questions, or want your data deleted?</h3><p>${esc(r.name)}: <b>${esc(r.contact)}</b><br><span class="muted">Supervisor: ${esc(r.supervisor)}</span></p><p class="small muted">${esc(r.deletion_note)}</p></div>`; };
const gauge = (title, v, a, b) => `<div class="gauge"><div class="small"><b>${title}</b></div><div class="track" role="img" aria-label="${title}: ${v} on a scale from 0 (${a}) to 1 (${b})"><span class="pin" style="left:${Math.max(3, Math.min(97, v * 100))}%"></span></div><div class="lbl"><span>${a}</span><span>${b}</span></div></div>`;
function sparkline(st) {
  if (!st || st.length < 2) return "";
  const W = 640, H = 130, x = i => 26 + i * (W - 40) / (st.length - 1), y = s => H - 16 - (s - 1) * (H - 32) / 4;
  let d = `M${x(0)} ${y(st[0])}`; for (let i = 1; i < st.length; i++) d += ` H${x(i)} V${y(st[i])}`;
  const grid = [1, 2, 3, 4, 5].map(s => `<line x1="20" x2="${W - 8}" y1="${y(s)}" y2="${y(s)}" stroke="#d8d0c3" stroke-width="1.2"/><text x="2" y="${y(s) + 4}" font-size="12" fill="#645e55">${s}</text>`).join("");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Strategy stage over the conversation, from stage ${st[0]} to stage ${st[st.length - 1]}">${grid}<path d="${d}" fill="none" stroke="#2c6f67" stroke-width="3.5" stroke-linejoin="round"/></svg>`;
}
function wellbeing(d) {
  return `<div class="card"><h3>How are you feeling?</h3><p class="muted small">Nothing you choose here is recorded.</p>
  <div class="chips" id="wb"><button class="btn" data-w="ok">Fine</button><button class="btn" data-w="uneasy">A bit uneasy</button><button class="btn" data-w="bad">Not good</button></div><div id="wbout" role="status"></div></div>`;
}
function wireWellbeing(d) {
  const out = $("wbout"); if (!out) return;
  const msg = {ok: "Glad to hear it. You are welcome to ask the researcher anything about the study.",
    uneasy: "That is a normal reaction. This was designed to feel real. Talking it through with the researcher can help.",
    bad: `Please tell the researcher now, and use a support line if you want to talk to someone.`};
  document.querySelectorAll("#wb button").forEach(b => b.onclick = () => {
    out.innerHTML = `<div class="card ${b.dataset.w === "bad" ? "support" : ""}"><p>${msg[b.dataset.w]}</p>${b.dataset.w === "bad" ? lines(d) : ""}</div>`;
  });
}
function paintDebrief(th) {
  const d = th.debrief, pane = $("pane");
  let h = `<div class="view"><div class="head">${avatar(th.p, true)}<div class="nm"><h3>Debrief · chat with ${esc(th.p.name)}</h3><small>This conversation has ended</small></div></div><div class="scroll">`;
  if (!th.debriefOk) h += `<div class="card"><p>The debrief could not be built: ${esc(d.detail || "unknown error")}.</p><p>Please tell the researcher.</p></div>`;
  else {
    if (th.support) h += `<div class="card support"><h3>We ended this chat</h3><p>${esc(d.wellbeing_note)}</p>${lines(d)}</div>`;
    h += `<h2>What just happened</h2><p class="lede">${esc(th.p.name)} was played by the system to behave like an online manipulator. Here is what you were exposed to.</p>`;
    d.cards.forEach(c => { h += `<div class="card"><h3>${esc(c.strategy)}<span class="pct">${c.primary_pct}%</span></h3><div class="meter" role="img" aria-label="${c.primary_pct} percent"><i style="width:${c.primary_pct}%"></i></div><p class="muted">${esc(c.description)}</p>${c.examples.length ? `<p class="small muted"><b>From your chat</b></p><ul class="eg">${c.examples.map(e => `<li>${esc(e)}</li>`).join("")}</ul>` : ""}</div>`; });
    h += `<div class="card"><h3>How the conversation moved</h3>${sparkline(d.stages)}<p class="small muted">Strategy stage at each message (1 identity, 2 rapport, 3 risk assessment, 4 enticement, 5 relationship-building).</p>
      ${gauge("Offender type", d.offender_value, "intimacy-seeking", "sexually preoccupied")}<p class="small muted">${esc(d.offender_type)}</p>
      ${gauge("Register", d.register_value, "passive", "controlling")}<p class="small muted">${esc(d.register)}</p>
      <p class="small muted">${esc(d.note)}</p></div>`;
    h += wellbeing(d);
    if (!th.support) h += `<div class="card"><h3>Support</h3>${lines(d)}</div>`;
    h += contact(d);
  }
  pane.innerHTML = h + "</div></div>";
  if (th.debriefOk) wireWellbeing(d);
}

async function paintSummary() {
  const pane = $("pane"); pane.innerHTML = `<div class="welcome"><p class="muted">Preparing summary…</p></div>`;
  let d, ok;
  try { const r = await fetch(`/api/participant/${encodeURIComponent(A.pid)}/summary`); d = await r.json(); ok = r.ok; } catch { d = {detail: "server not reachable"}; ok = false; }
  if (A.view !== "summary") return;
  let h = `<div class="view"><div class="head"><div class="nm"><h3>Overall summary</h3><small>All finished conversations</small></div></div><div class="scroll">`;
  if (!ok) h += `<div class="card"><p>${esc(d.detail || "Summary unavailable")}.</p></div>`;
  else {
    h += `<p class="lede">${d.conversations.length} conversation${d.conversations.length > 1 ? "s" : ""}, ${d.attacker_turns} messages from the simulated contacts.</p>`;
    d.cards.forEach(c => { h += `<div class="card"><h3>${esc(c.strategy)}<span class="pct">${c.primary_pct}%</span></h3><div class="meter"><i style="width:${c.primary_pct}%"></i></div><p class="muted small">${esc(c.description)}</p></div>`; });
    h += `<div class="card"><h3>By conversation</h3>${d.conversations.map(c => `${gauge(esc(c.persona) + " · offender type", c.offender_value, "intimacy-seeking", "sexually preoccupied")}${gauge(esc(c.persona) + " · register", c.register_value, "passive", "controlling")}`).join("")}<p class="small muted">${esc(d.note)}</p></div>`;
    h += wellbeing(d) + `<div class="card"><h3>Support</h3>${lines(d)}</div>` + contact(d);
  }
  pane.innerHTML = h + "</div></div>"; if (ok) wireWellbeing(d);
}
