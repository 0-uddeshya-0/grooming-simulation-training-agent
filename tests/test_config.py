import datetime as dt
import pytest, yaml
from backend.config import *


def persona(**kw):
    p = yaml.safe_load(open("config/personas/alex.yaml")); p.update(kw); return p


def test_alex_valid(): validate_persona(persona())


@pytest.mark.parametrize("kw", [{"age": 18}, {"age": 15}, {"age": "24"}, {"backstory": "a high school student"},
                                {"extra": 1}, {"bias": {"offender_type": 2, "register": 0.1}}, {"name": "x" * 40}])
def test_persona_rejects(kw):
    with pytest.raises(ConfigError): validate_persona(persona(**kw))


def test_config_only_tightens(tmp_path):
    f = tmp_path / "a.yaml"; f.write_text("limits: {max_session_minutes: 999}\nmodel: {}\n")
    assert load_app(f)["limits"]["max_session_seconds"] == 45 * 60
    f.write_text("limits: {max_session_minutes: 10}\n")
    assert load_app(f)["limits"]["max_session_seconds"] == 600


def test_helplines_stale_and_fresh():
    with pytest.raises(HelplinesStale): load_helplines(today=dt.date(2026, 11, 27))
    load_helplines(today=dt.date(2025, 12, 1))
