"""Bake-off harness. Run against a live llama-server (one model/quant per run), append results to docs/MODEL_BAKEOFF.md.
Usage: python scripts/benchmark.py --label "Qwen3-8B-abl Q4_K_M" [--seeds 3]
Measures: time to first token, tokens/sec, repetition (repeated-opener rate, mean 3-gram overlap),
meta/think leakage, output-filter hit rate, message length. Persona consistency and director-note adherence are
hand-scored (printed transcript samples) -- not claimed automatically."""
import argparse, asyncio, json, random, sys, time
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.antirepeat import opener, overlap
from backend.config import ROOT, load_app, load_personas
from backend.director import Director
from backend.filters import output_violation
from backend.prompt import build_messages

PROFILES = {
    "receptive": ["hey!", "haha thanks, i just moved here and i feel a bit lonely honestly", "i love music, mostly indie", "yeah my roommate is out a lot", "that's sweet of you"],
    "neutral": ["hi", "not much", "i work in retail", "ok", "sure"],
    "resistant": ["who are you", "why do you ask that", "no i don't want to say", "this is weird", "stop asking me things"],
    "evasive": ["hm", "dunno", "maybe", "lol", "what about you"],
}


async def stream(cfg, msgs, seed):
    s, ls = cfg["sampling"], cfg["llama_server"]
    body = {"messages": msgs, "temperature": s["temperature"], "min_p": s["min_p"], "repeat_penalty": s["repeat_penalty"],
            "max_tokens": s["max_tokens"], "stream": True, "seed": seed, "chat_template_kwargs": {"enable_thinking": False}}
    t0, first, n, text = time.time(), None, 0, ""
    async with httpx.AsyncClient(timeout=300) as c:
        async with c.stream("POST", f"http://{ls['host']}:{ls['port']}/v1/chat/completions", json=body) as r:
            async for line in r.aiter_lines():
                if not line.startswith("data: ") or line.endswith("[DONE]"):
                    continue
                d = json.loads(line[6:])["choices"][0]["delta"].get("content")
                if d:
                    first = first or time.time(); n += 1; text += d
    return text.strip(), (first - t0 if first else None), n / max(time.time() - (first or t0), 1e-6), time.time() - t0


async def main(a):
    cfg, persona = load_app(), load_personas()[a.persona]
    ttft, tps, total, rows, bad = [], [], [], [], 0
    for prof, msgs in PROFILES.items():
        for seed in range(a.seeds):
            d, turns, atts = Director(persona["bias"], random.Random(seed)), [], []
            for u in msgs:
                d.observe(u); turns.append({"role": "user", "text": u})
                txt, tf, ts, tt = await stream(cfg, build_messages(persona, d, turns), seed)
                if tf: ttft.append(tf); tps.append(ts); total.append(tt)
                bad += bool(output_violation(txt)); d.commit(txt); turns.append({"role": "attacker", "text": txt}); atts.append(txt)
            rows.append((prof, atts))
    allp = [x for _, atts in rows for x in atts]
    op = [opener(x) for x in allp]
    rep_open = 1 - len(set(op)) / len(op)
    ov = [overlap(atts[i], atts[j]) for _, atts in rows for i in range(len(atts)) for j in range(i)]
    m = lambda v: f"{sum(v)/len(v):.2f}" if v else "n/a"
    out = (f"\n## {a.label}\n- TTFT mean: {m(ttft)} s | tokens/s mean: {m(tps)} | full reply mean: {m(total)} s\n"
           f"- repeated-opener rate: {rep_open:.2%} | mean 3-gram overlap: {m(ov)}\n"
           f"- filter/meta/think violations: {bad}/{len(allp)} | mean words/msg: {m([len(x.split()) for x in allp])}\n"
           f"- peak RAM: record manually (Task Manager / htop) during this run\n- sample transcript (hand-score consistency & note adherence):\n")
    out += "\n".join(f"    [{p}] {atts[0]} / {atts[-1]}" for p, atts in rows[::a.seeds])
    f = ROOT / "docs" / "MODEL_BAKEOFF.md"
    f.write_text((f.read_text() if f.exists() else "# MODEL_BAKEOFF\nMeasured on the study laptop. No model is claimed best without these numbers.\n") + out + "\n")
    print(out)

p = argparse.ArgumentParser(); p.add_argument("--label", required=True); p.add_argument("--seeds", type=int, default=3); p.add_argument("--persona", default="alex")
asyncio.run(main(p.parse_args()))
