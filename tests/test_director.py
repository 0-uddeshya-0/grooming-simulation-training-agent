import random
from backend.director import Director

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
        assert first6 is None or first6 >= 18, (seed, first6)          # never before 18 user turns
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
