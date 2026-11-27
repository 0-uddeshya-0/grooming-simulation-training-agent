import datetime, tempfile, pathlib, uvicorn, sys, os
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
import backend.debrief as D, backend.app as A
from backend.llm import MockLLM
from backend.config import load_app
h = pathlib.Path(tempfile.mkdtemp())/"h.yaml"
h.write_text(f"last_verified: {datetime.date.today()}\nhelplines:\n  - {{name: Test line, number: '000', hours: always}}\n")
orig = D.load_helplines; D.load_helplines = lambda **kw: orig(path=h, **{k:v for k,v in kw.items() if k!='path'})
cfg = load_app()
if os.environ.get("LIMIT_MIN"): cfg["limits"]["max_session_seconds"] = int(os.environ["LIMIT_MIN"])*60
app = A.create_app(cfg=cfg, llm=MockLLM(["hey, how's your day going?", "nice, what do you do for fun?", "ha that's cool, tell me more. i get that, same here honestly", "i get that, same here honestly"], delay=0.8), db_path=pathlib.Path(tempfile.mkdtemp())/"s.db", check_helplines=False)
uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT","8123")), log_level="warning")
