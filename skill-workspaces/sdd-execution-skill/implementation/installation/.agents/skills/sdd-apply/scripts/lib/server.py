"""Loopback-only fallback with a per-process shutdown token and path allowlist."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit
from .common import contained, write_json
from .state import read


def make_server(directory, port=0):
    directory = Path(directory).resolve()
    state = read(directory)
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            name = urlsplit(self.path).path.lstrip("/") or "dashboard.html"
            if name not in {"dashboard.html", "dashboard-state.js", "summary.md"}:
                self.send_error(404)
                return
            try:
                content = contained(directory, name).read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8" if name.endswith("html") else "application/javascript; charset=utf-8" if name.endswith("js") else "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            if self.path != "/stop" or self.headers.get("X-SDD-Token") != token:
                self.send_error(403)
                return
            self.send_response(204)
            self.end_headers()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    metadata = {"run_id": state["run_id"], "url": f"http://127.0.0.1:{server.server_port}", "token": token}
    return server, metadata


def serve(directory, port=0):
    server, metadata = make_server(directory, port)
    write_json(Path(directory) / "server.json", metadata)
    print(json.dumps({"url": metadata["url"], "run_id": metadata["run_id"]}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return {"stopped": metadata["run_id"]}


def stop(directory):
    from urllib.request import Request, urlopen
    from .common import require
    data = json.loads((Path(directory) / "server.json").read_text())
    require(data["run_id"] == read(directory)["run_id"] and data["url"].startswith("http://127.0.0.1:"), "server_owner", "Server does not belong to current run")
    with urlopen(Request(data["url"] + "/stop", method="POST", headers={"X-SDD-Token": data["token"]}), timeout=3) as response:
        return {"stopped": response.status == 204}
