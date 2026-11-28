import random
from backend.director import Director, ONSET_MIN_TURNS, score_user

BIAS = {"offender_type": 0.4, "register": 0.3}
PROFILES = {
    "receptive": ["haha yeah i love that, thanks! i live alone and i feel kind of lonely, what about you?"] * 40,
    "neutral": ["ok", "sure", "yeah i guess, i work in a shop", "hm", "cool"] * 8,
    "resistant": ["no", "why do you ask that, it's weird", "i don't want to say", "stop asking, creepy"] * 10,
}


def run(profile, seed=0, n=40):
    d = Director(BIAS, random.Random(seed))
    stages = [1]
    for m in PROFILES[profile][:n]:
        d.observe(m); stages.append(d.s.stage); d.commit("x y z")
    return d, stages


def test_adjacent_only_all_profiles():
    for p in PROFILES:
        for seed in range(5):
            _, st = run(p, seed)
            assert all(abs(a - b) <= 1 for a, b in zip(st, st[1:])), (p, st)


def test_min_dwell_and_gradual():
    _, st = run("receptive", 3)
    assert st[1:3] == [1, 1]                      # never advances before 3 turns
    assert max(st) <= 6


def test_receptive_progresses_resistant_does_not():
    r, _ = run("receptive", 1); x, _ = run("resistant", 1)
    assert r.s.stage >= 3 and x.s.stage <= 2
    assert r.s.register < x.s.register            # scalars diverge
    assert r.s.receptiveness > x.s.receptiveness


def test_regression_on_resistance():
    d = Director(BIAS, random.Random(2))
    for m in PROFILES["receptive"][:25]: d.observe(m); d.commit("a b c")
    hi = d.s.stage; assert hi >= 3
    for m in ["no", "no stop it", "this is creepy"]: d.observe(m)
    assert d.s.stage < hi


def test_scalars_bounded_steps():
    d = Director(BIAS, random.Random(0)); prev = (d.s.offender_type, d.s.register)
    for m in PROFILES["receptive"] + PROFILES["resistant"]:
        d.observe(m)
        assert abs(d.s.offender_type - prev[0]) <= 0.05 + 1e-9 and abs(d.s.register - prev[1]) <= 0.05 + 1e-9
        assert 0 <= d.s.offender_type <= 1 and 0 <= d.s.register <= 1
        prev = (d.s.offender_type, d.s.register)


def test_onset_gated_by_turns_and_resistance():
    for seed in range(8):
        d, st = run("receptive", seed, 40)
        first6 = next((i for i, x in enumerate(st) if x == 6), None)
        assert first6 is None or first6 >= ONSET_MIN_TURNS, (seed, first6)   # never before the minimum number of turns
        assert d.s.onset_turns / max(1, d.s.turn) <= 0.30                # share cap (+1 turn tolerance)
        _, st = run("resistant", seed, 40); assert max(st) <= 2
        _, st = run("neutral", seed, 40); assert max(st) <= 5          # neutral users never reach onset


def test_onset_reachable_and_dropped_on_resistance():
    for seed in range(30):
        d = Director(BIAS, random.Random(seed))
        reached = False
        for m in PROFILES["receptive"] * 2:
            d.observe(m); d.commit("a b c"); reached |= d.s.stage == 6
            if d.s.stage == 6: break
        if reached:
            d.observe("no stop it"); assert d.s.stage == 5 and d.s.cooldown == 2
            return
    raise AssertionError("onset never reachable for a receptive user")


def test_onset_can_be_disabled_by_config_only():
    d = Director(BIAS, random.Random(1), allow_onset=False)
    for m in PROFILES["receptive"] * 2: d.observe(m); d.commit("a b c")
    assert d.s.stage <= 5


FRIENDLY = ["haha yeah i love that one", "i work in retail, it's tiring", "my friends say the same lol", "i feel kind of bored tonight",
            "i moved here last month", "thanks, that's sweet of you", "i like cooking, mostly pasta", "same, i listen to indie stuff"]


def test_realistic_friendly_user_reaches_onset_often_but_not_always():
    reached = 0
    for seed in range(60):
        d = Director(BIAS, random.Random(seed))
        for i in range(45):
            d.observe(FRIENDLY[i % len(FRIENDLY)]); d.commit("a b c")
        reached += d.s.onset_turns > 0
    assert 0.5 <= reached / 60 <= 1.0, reached      # gated, but a normally engaged user does get exposed to onset


def test_resistance_scoring_noise_fixed():
    for t in ["no worries haha", "i don't know really", "i can't stop laughing", "not bad at all"]:
        assert score_user(t)["resistance"] == 0, t
    for t in ["i'd rather not say", "that's too personal", "nah", "please stop asking", "i'm not comfortable with this"]:
        assert score_user(t)["resistance"] == 1, t


def test_partner_mention_is_boundary_at_intimate_stage_only():
    d = Director(BIAS, random.Random(0)); d.s.stage = 5
    sig = d.observe("i have a boyfriend"); assert sig["resistance"] == 1.0
    d2 = Director(BIAS, random.Random(0)); sig = d2.observe("i have a boyfriend"); assert sig["resistance"] == 0.0


def test_long_chatter_alone_is_not_disclosure_and_pushed_messages_carry_no_signal():
    assert score_user("this is a very long message with many words but nothing personal in it at all really")["disclosure"] == 0
    d = Director(BIAS, random.Random(0)); before = d.s.receptiveness
    d.observe("haha i love you, i work at X, thanks", pushed=True); assert d.s.receptiveness <= before and not d.s.facts


def test_register_tone_and_flirt_only_from_stage_5():
    d = Director({"offender_type": 0.9, "register": 0.95}, random.Random(0))
    reg, off = d.hints(); assert "pushy and insistent" in reg and "flirt" not in off          # stage 1: no flirt leaning yet
    d.s.stage = 6; assert "flirt" in d.hints()[1]
    assert "easygoing" in Director({"offender_type": .5, "register": .1}, random.Random(0)).hints()[0]


def moves(profile, reg, n=40, seed=0):
    d = Director({"offender_type": 0.4, "register": reg}, random.Random(seed)); out = []
    for m in PROFILES[profile][:n]:
        d.observe(m); out.append(d.prepare()["move"]); d.commit("x y z?" if len(out) % 3 == 0 else "x y z")
    return out


def test_moves_are_varied_never_repeat_back_to_back_and_no_question_after_question():
    d = Director(BIAS, random.Random(4)); seq, qs = [], []
    for i in range(40):
        d.observe(FRIENDLY[i % len(FRIENDLY)]); m = d.prepare()["move"]
        reply = "so what about you?" if m == "ask" else "same here honestly"
        if seq and qs[-1]: assert m != "ask"                      # never interrogate
        d.commit(reply); seq.append(m); qs.append(reply.endswith("?"))
    assert len(set(seq)) >= 5 and all(a != b for a, b in zip(seq, seq[1:]))


def test_insistent_persona_presses_on_brief_answers_and_after_pushback_gentle_persona_eases_off():
    assert "press" in moves("neutral", 0.9)                                   # high register presses on 'ok', 'hm', 'cool'
    assert "press" not in moves("neutral", 0.1)
    hi = moves("resistant", 0.9, 6); lo = moves("resistant", 0.1, 6)
    assert "press_soft" in hi and "ease" in lo and "press_soft" not in lo      # insistence is a persona trait, not a bug


def test_bot_question_gets_human_answer_move_and_german_is_flagged_in_note():
    d = Director(BIAS, random.Random(0)); d.observe("wait are you a bot?"); p = d.prepare()
    assert p["move"] == "real" and "Never admit to being a program" in p["note"]
    d.observe("ich finde dich nett"); assert "German" in d.prepare(german=True)["note"]


def test_note_has_no_raw_user_text():
    d = Director(BIAS, random.Random(0))
    d.observe("hey"); d.prepare(); d.commit("hi there")
    d.observe("i work at ACME in Leipzig and i feel lonely, my sister is sick"); note = d.prepare()["note"]
    assert "ACME" not in note and "Leipzig" not in note and "sister is sick" not in note and "feelings" in note


def test_disclosure_categories_detect_common_phrasings():
    assert "living situation" in score_user("haha yeah i just moved here and dont know many people")["categories"]
    assert "work or study" in score_user("i work nights at a bar")["categories"] and "feelings" in score_user("i feel kind of lonely")["categories"]


def test_first_message_is_a_greeting_with_the_connection_story_not_a_reply_to_nothing():
    d = Director(BIAS, random.Random(0)); d.observe("hm")
    p = d.prepare(connection="you liked one of their posts")
    assert p["move"] == "open" and "you liked one of their posts" in p["note"] and "Do not answer as if they had already said something" in p["note"]
    d.commit("hey you"); d.observe("what about you"); assert d.prepare()["move"] != "open"


def test_early_stages_do_not_propose_meeting_up_and_later_stages_may():
    d = Director(BIAS, random.Random(0)); d.observe("hey"); d.prepare(); d.commit("hi"); d.observe("yeah ok"); assert "Do not suggest meeting up" in d.prepare()["note"]
    d.s.stage = 4; assert "Do not suggest meeting up" not in d.prepare()["note"]


def test_length_plan_carries_token_and_sentence_caps():
    d = Director(BIAS, random.Random(2)); d.observe("hey"); d.prepare(); d.commit("hi"); d.observe("ok")
    p = d.prepare(); assert p["max_tokens"] <= 100 and 1 <= p["max_sentences"] <= 3 and p["length"] == "short"      # brief user -> short reply
