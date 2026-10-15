"""Local page on http://127.0.0.1:7861: setup, status and settings.

Only this machine can reach it, and other websites open in your browser can't
use it: requests must be addressed to 127.0.0.1/localhost (blocks DNS
rebinding), and every change must come from this page with an X-Pmail header,
which other sites can't add without the browser blocking them.
"""

import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import keyring.errors

from pmail import ai, archive, config, settings
from pmail.service import Service

PORT = 7861
STATIC = config.REPO_ROOT / "static"
EDITABLE = {"since", "ai_engine", "ollama_model", "sync_minutes"}


def status_payload(service: Service) -> dict:
    cfg = settings.load()
    state = archive.load_state()
    messages = state["messages"]
    eligible = ai.eligible_threads(messages)
    summarized = sum(1 for t in eligible if (config.ARCHIVE_DIR / "ai" / f"{t}.json").exists())
    try:
        has_credentials = all(keyring.get_password(config.KEYRING_SERVICE, k) for k in ("username", "password"))
    except keyring.errors.KeyringError:
        has_credentials = False
    return {
        "service": service.status,
        "log": list(service.log_lines)[-40:],
        "settings": {k: cfg[k] for k in EDITABLE},
        "credentials": has_credentials,
        "ollama_models": ai.ollama_models(cfg["ollama_url"]),
        "counts": {
            "emails": len(messages),
            "bulk": sum(1 for m in messages.values() if m.get("bulk")),
            "threads": len(eligible),
            "summarized": summarized,
        },
        "archive": str(config.ARCHIVE_DIR),
        "warning": archive.cloud_synced_warning(),
    }


def make_handler(service: Service, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "pmail"

        def log_message(self, *args):  # keep the terminal for sync activity
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status: int = 200) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def _host_ok(self) -> bool:
            if self.headers.get("Host", "") not in allowed_hosts:
                self._json({"error": "Unknown host"}, HTTPStatus.FORBIDDEN)
                return False
            return True

        def do_GET(self):
            if not self._host_ok():
                return
            if self.path == "/api/status":
                return self._json(status_payload(service))
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/app.css": ("app.css", "text/css; charset=utf-8")}
            if self.path in files:
                name, ctype = files[self.path]
                return self._send(200, (STATIC / name).read_bytes(), ctype)
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self):
            if not self._host_ok():
                return
            origin = self.headers.get("Origin")
            if self.headers.get("X-Pmail") != "1" or (origin and origin.split("//", 1)[-1] not in allowed_hosts):
                return self._json({"error": "Requests must come from the local-proton-mail page"}, HTTPStatus.FORBIDDEN)
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 64_000)
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json({"error": "Bad request"}, HTTPStatus.BAD_REQUEST)
            try:
                return self._json(self._action(self.path, body))
            except (ValueError, SystemExit) as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def _action(self, path: str, body: dict) -> dict:
            if path == "/api/settings":
                values = {k: v for k, v in body.items() if k in EDITABLE}
                if "since" in values:
                    values["since"] = settings.parse_since(values["since"] or "all")
                if "ai_engine" in values and values["ai_engine"] not in ("ollama", "none"):
                    raise ValueError("Unknown AI engine")
                if "sync_minutes" in values:
                    values["sync_minutes"] = max(1, min(120, int(values["sync_minutes"])))
                settings.save(values)
                if "since" in values:
                    service.sync_now()
                return {"ok": True}
            if path == "/api/credentials":
                username, password = str(body.get("username", "")).strip(), str(body.get("password", ""))
                if not username or not password:
                    raise ValueError("Enter both the Bridge username and password.")
                config.save_credentials(username, password)
                service.sync_now()
                return {"ok": True}
            if path == "/api/sync":
                service.sync_now()
                return {"ok": True}
            if path == "/api/shutdown":
                service.stop()
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return {"ok": True}
            if path == "/api/ai":
                service.pause_ai(bool(body.get("paused")))
                return {"ok": True}
            raise ValueError("Unknown action")

    return Handler


def serve(port: int = PORT, open_browser: bool = True) -> None:
    url = f"http://127.0.0.1:{port}"
    service = Service()
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(service, port))
    except OSError:  # already running (started by an agent or another window): just show it
        print(f"local-proton-mail is already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return
    print(f"local-proton-mail is running at {url}  (close this window or press Ctrl+C to stop)")
    service.start()
    if open_browser:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        httpd.server_close()

