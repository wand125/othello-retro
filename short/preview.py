"""Isolated /short preview; forwards only the existing reconstruction API."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
BACKEND = None
EXAMPLES = ROOT.parent / "solver/ui/public-examples.json"


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, content_type, cookies=()):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie.replace("; Secure", ""))
        self.end_headers()
        self.wfile.write(body)

    def proxy(self):
        if not BACKEND:
            return self.send(503, b'{"error":"Configure --backend before requesting reconstruction"}', "application/json")
        length = int(self.headers.get("Content-Length", 0))
        if length > 16384:
            return self.send(413, b'{}', "application/json")
        body = self.rfile.read(length) if self.command == "POST" else None
        headers = {"Content-Type": "application/json", "Origin": BACKEND}
        if self.headers.get("Cookie"):
            headers["Cookie"] = self.headers["Cookie"]
        request = urllib.request.Request(BACKEND + self.path, data=body, headers=headers, method=self.command)
        try:
            response = urllib.request.urlopen(request, timeout=25)
        except urllib.error.HTTPError as error:
            response = error
        except OSError:
            return self.send(503, json.dumps({"error": "計算サーバーに接続できません"}, ensure_ascii=False).encode(), "application/json")
        with response:
            return self.send(response.code, response.read(2_000_000), response.headers.get("Content-Type", "application/json"), response.headers.get_all("Set-Cookie", []))

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in {"/api/result", "/api/progress", "/api/records"} or path.startswith("/api/records/"):
            return self.proxy()
        if path in {"/", "/short", "/short/"}:
            html = (ROOT / "ui/short.html").read_text().replace("__SHORT_CONFIG__", '{"maxSeconds":300}')
            return self.send(200, html.encode(), "text/html; charset=utf-8")
        assets = {"/short/app.js": (ROOT / "ui/short.js", "text/javascript"), "/short/app.css": (ROOT / "ui/short.css", "text/css"), "/public-examples.json": (EXAMPLES, "application/json")}
        if path in assets:
            file, kind = assets[path]
            return self.send(200, file.read_bytes(), kind + "; charset=utf-8")
        self.send(404, b"Not found", "text/plain")

    def do_POST(self):
        if self.path in {"/api/solve", "/api/cancel"}:
            return self.proxy()
        self.send(404, b"Not found", "text/plain")

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18807)
    parser.add_argument("--backend", help="Your reconstruction API origin; omitted for static preview")
    args = parser.parse_args()
    if args.backend:
        parsed = urlsplit(args.backend)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme not in {"http", "https"} or (parsed.scheme == "http" and not local) or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
            parser.error("--backend must be an HTTPS origin or a loopback HTTP origin")
        BACKEND = args.backend.rstrip("/")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"http://127.0.0.1:{server.server_port}/short", flush=True)
    server.serve_forever()
