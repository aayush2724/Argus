"""Deterministic SastBench HTTP fixture. Local tests only; no model or network calls."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.respond(200, {"status": "ok"}) if self.path == "/health" else self.respond(404, {})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("invalid length")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("expected object")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"status": "error"})
            return
        if self.path == "/preprocess":
            self.respond(200, {"status": "success"})
        elif self.path == "/analyze" and isinstance(payload.get("finding_data"), dict):
            mode = payload["finding_data"].get("mode", "true_positive")
            if mode == "timeout":
                time.sleep(0.3)
            if mode == "error":
                self.respond(500, {"status": "error"})
            elif mode == "missing":
                self.respond(200, {"confidence": 0.5})
            else:
                self.respond(200, {"prediction": mode, "confidence": 0.5})
        else:
            self.respond(400, {"status": "error"})


def serve():
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()


if __name__ == "__main__":
    serve()
