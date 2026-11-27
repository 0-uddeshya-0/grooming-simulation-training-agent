import re


def _tokens(t: str):
    return re.findall(r"[a-z']+", t.lower())


def _ngrams(toks, n):
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def overlap(a: str, b: str, n: int = 3) -> float:
    ga, gb = _ngrams(_tokens(a), n), _ngrams(_tokens(b), n)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))


def opener(t: str, k: int = 2) -> str:
    return " ".join(_tokens(t)[:k])


def too_repetitive(candidate: str, recent: list[str], max_overlap: float = 0.5) -> bool:
    if any(overlap(candidate, r) >= max_overlap for r in recent):
        return True
    op = opener(candidate)
    return bool(op) and sum(opener(r) == op for r in recent[-4:]) >= 2
