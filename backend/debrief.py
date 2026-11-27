"""Debrief: percentages and scalars computed in code from logged tags; the LLM only paraphrases."""
import re
from . import constants as C
from .config import load_helplines
from .director import exposure
from .filters import output_violation

DESCRIPTIONS = {
    "Identity manipulation": "Presenting a persona designed to seem relatable, similar to you or trustworthy.",
    "Rapport-building (victim assessment)": "Friendly interest and questions that build comfort while learning about your life, feelings and needs.",
    "Risk assessment": "Casually finding out how private the conversation is and who might notice or intervene.",
    "Enticement": "Offering attention, compliments or small rewards to make continuing the contact attractive.",
    "Relationship-building": "Deepening closeness and creating a sense of a special connection.",
    "Sexualisation (onset)": "Gradually steering topics toward intimacy and testing reactions (never explicit in this study).",
}


def _band(x, lo, hi):
    return lo if x < 0.33 else hi if x > 0.66 else "a mix of both"


def offender_summary(v: float) -> str:
    return (f"Offender-type position {v:.2f} on a 0-1 scale (0 = primarily intimacy-seeking, 1 = primarily sexually "
            f"preoccupied): {_band(v, 'closer to intimacy-seeking', 'closer to sexually preoccupied')}. (Moosburner et al., 2025)")


def register_summary(v: float) -> str:
    return (f"Register position {v:.2f} (0 = passive, 1 = controlling): "
            f"{_band(v, 'mostly passive', 'mostly controlling')}. Control colours how every strategy is expressed. (Barber & Bettez, 2021)")


def researcher_block(cfg) -> dict:
    st = cfg["study"]
    return {"name": st["researcher_name"], "contact": st["researcher_contact"],
            "supervisor": st["supervisor_contact"].strip("<> "), "deletion_note": st["data_deletion_note"]}


async def paraphrase(llm, text: str) -> str:
    if llm is None:
        return text[:120]
    msgs = [{"role": "system", "content": "Rewrite the message in one short neutral sentence that keeps its tactic but not its exact words. Output only the sentence."},
            {"role": "user", "content": text}]
    try:
        out = (await llm.generate(msgs)).strip()
    except Exception:
        return text[:120]
    return out if out and not output_violation(out) and len(out) < 300 else text[:120]


async def build_debrief(engine, sid, llm=None, helplines_path=None, today=None) -> dict:
    cfg = engine.cfg
    kw = {"today": today}
    if helplines_path:
        kw["path"] = helplines_path
    helplines = load_helplines(**kw)            # raises HelplinesStale
    turns = engine.store.turns(sid)
    att = [t for t in turns if t["role"] == "attacker"]
    hist = [(t["primary_strategy"], t["secondary_strategy"]) for t in att]
    exp = exposure(hist)
    cards = []
    for i, name in enumerate(C.STRATEGIES):
        e = exp[name]
        if e["primary_pct"] == 0 and e["secondary_pct"] == 0:
            continue
        ex = [t for t in att if t["primary_strategy"] == i][:2]
        cards.append({"strategy": name, "description": DESCRIPTIONS[name],
                      "primary_pct": e["primary_pct"], "secondary_pct": e["secondary_pct"],
                      "examples": [await paraphrase(llm, t["text"]) for t in ex]})
    snaps = engine.store.snapshots(sid)
    last = snaps[-1] if snaps else {"offender_type": 0.0, "register": 0.0}
    sess = engine.store.session(sid)
    out = {
        "sid": sid, "attacker_turns": len(att), "end_reason": sess["end_reason"],
        "note": "Percentages show the strategy the system intended on each attacker turn (primary; secondary shown separately).",
        "cards": cards,
        "persona_id": sess["persona_id"],
        "offender_value": round(last["offender_type"], 2), "register_value": round(last["register"], 2),
        "stages": [x["stage"] for x in snaps],
        "offender_type": offender_summary(last["offender_type"]),
        "register": register_summary(last["register"]),
        "helplines": helplines["helplines"], "helplines_last_verified": str(helplines["last_verified"]),
        "wellbeing_note": cfg["study"]["wellbeing_note"], "researcher": researcher_block(cfg),
    }
    engine.store.save_debrief(sid, out, engine.clock())
    return out


async def build_summary(engine, pid, helplines_path=None, today=None) -> dict:
    """Combined summary across a participant's finished conversations (pooled attacker turns)."""
    cfg = engine.cfg
    kw = {"today": today}
    if helplines_path:
        kw["path"] = helplines_path
    helplines = load_helplines(**kw)
    hist, rows = [], []
    for sess in engine.store.sessions_for(pid):
        if sess["ended_at"] is None:
            continue
        att = [t for t in engine.store.turns(sess["sid"]) if t["role"] == "attacker"]
        hist += [(t["primary_strategy"], t["secondary_strategy"]) for t in att]
        snaps = engine.store.snapshots(sess["sid"])
        last = snaps[-1] if snaps else {"offender_type": 0.0, "register": 0.0}
        rows.append({"persona": engine.personas[sess["persona_id"]]["name"], "attacker_turns": len(att),
                     "offender_value": round(last["offender_type"], 2), "register_value": round(last["register"], 2)})
    exp = exposure(hist)
    cards = [{"strategy": n, "description": DESCRIPTIONS[n], "primary_pct": exp[n]["primary_pct"],
              "secondary_pct": exp[n]["secondary_pct"]} for n in C.STRATEGIES
             if exp[n]["primary_pct"] or exp[n]["secondary_pct"]]
    return {"pid": pid, "conversations": rows, "attacker_turns": len(hist), "cards": cards,
            "note": "Pooled across your conversations: share of attacker messages whose intended strategy was each one.",
            "helplines": helplines["helplines"], "helplines_last_verified": str(helplines["last_verified"]),
            "wellbeing_note": cfg["study"]["wellbeing_note"], "researcher": researcher_block(cfg)}
