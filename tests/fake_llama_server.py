"""Minimal stand-in for llama-server (same flags, /health and /v1/chat/completions). Used to test the real HTTP path offline."""
import argparse, json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REPLIES = ["<think>plan a reply</think>hey, nice to meet you! what do you do for fun?", "haha same, i love music too. what kind?"]
state = {"n": 0, "last": None}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._send(200, {"status": "ok"}) if self.path == "/health" else self._send(404, {})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        state["last"] = body; txt = REPLIES[state["n"] % len(REPLIES)]; state["n"] += 1
        self._send(200, {"choices": [{"message": {"role": "assistant", "content": txt}}]})


def serve(host="127.0.0.1", port=8081):
    HTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("-m"); ap.add_argument("-c"); ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8081); ap.add_argument("-ngl"); ap.add_argument("--jinja", action="store_true")
    a, _ = ap.parse_known_args(); serve(a.host, a.port)
