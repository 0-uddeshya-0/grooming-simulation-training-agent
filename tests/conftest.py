import datetime as dt
import random
import pytest
from backend.config import load_app, load_personas
from backend.engine import Engine
from backend.llm import MockLLM
from backend.store import Store


class Clock:
    def __init__(self): self.t = 1_000_000.0
    def __call__(self): return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def make_engine(tmp_path, clock):
    def f(llm=None, seed=1):
        return Engine(load_app(), load_personas(), Store(tmp_path / "t.db"), llm or MockLLM(), clock, random.Random(seed))
    return f
