"""Temporary HTTP listener used while a first-run deployment imports data."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class BootstrapHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"ok": True, "status": "bootstrapping"}).encode()
            status = 200
        else:
            body = b"NHL GM is importing the 2025-26 league baseline. Please retry shortly."
            status = 503
        self.send_response(status)
        self.send_header("Content-Type", "application/json" if self.path == "/health" else "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    print(f"Bootstrap listener binding to http://{args.host}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), BootstrapHandler).serve_forever()


if __name__ == "__main__":
    main()
