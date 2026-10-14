"""Local HTTP endpoint so the landing page form can send the profile JSON straight to the app.

    POST http://127.0.0.1:47800/profile   body: onboarding JSON
    POST http://127.0.0.1:47800/learn     body: {"title", "content", "category"}
    GET  http://127.0.0.1:47800/status
Only binds to localhost.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import knowledge, profile
from .db import db


def start(port: int, on_profile):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path.rstrip("/") == "/status":
                prof = db.get_profile()
                return self._send(200, {"ok": True, "app": "NEXUS", "profile": bool(prof)})
            self._send(404, {"ok": False})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(min(length, 2_000_000)) or b"{}")
                if self.path.rstrip("/") == "/profile":
                    prof = profile.import_profile(data)
                    on_profile(prof)
                    return self._send(200, {"ok": True, "name": prof["name"]})
                if self.path.rstrip("/") == "/learn":
                    result = knowledge.learn(data["title"], data["content"], data.get("category", "aprendido"))
                    return self._send(200, {"ok": True, **result})
                self._send(404, {"ok": False})
            except (ValueError, KeyError) as exc:
                self._send(400, {"ok": False, "error": str(exc)})

        def log_message(self, *args):
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        return None  # port busy (another NEXUS running?) - the app works without the bridge
    threading.Thread(target=server.serve_forever, daemon=True, name="bridge").start()
    return server
