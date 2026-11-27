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
    assert max(st) <= 5


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
