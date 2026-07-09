"""
ST185 Celica repair-manual desktop app.

Runs a private local web server (in-process, no console, no-cache headers)
and shows the manual app in a native WebView2 window. Packaged with
PyInstaller into CelicaManual.exe — no browser, no downloads, no Adobe.

The server also exposes a small localhost-only JSON API so the app's
"Add manuals" panel can accept new PDFs and rebuild the catalog in place:
    POST /api/upload    raw PDF body + X-Filename header -> saves to manuals\
    POST /api/rebuild   runs the catalog builder in a background thread
    GET  /api/status    {running, done, error, log: [...last lines...]}

CLI:  app.py [--server-only] [--port N]
    --server-only   start the server, print "SERVING <url>", no window
                    (used for headless testing / running under a browser)
"""
import json
import os
import socket
import subprocess
import sys
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_TITLE = "ST185 Celica GT-Four / All-Trac — Repair Manual"
MAX_UPLOAD = 100 * 1024 * 1024      # 100 MB per PDF


def find_base() -> Path:
    """Locate the package root (contains celica-manual/index.html),
    whether the exe sits in the package root or inside celica-manual."""
    if getattr(sys, "frozen", False):
        here = Path(sys.executable).resolve().parent
    else:
        here = Path(__file__).resolve().parent
    for cand in (here, here.parent, here.parent.parent):
        if (cand / "celica-manual" / "index.html").is_file():
            return cand
    raise SystemExit("Could not find celica-manual/index.html near the exe.")


BASE = find_base()
MANUALS = BASE / "manuals"

# ---------------------------------------------------------------------------
# Rebuild state (one build at a time, log captured for /api/status polling)
# ---------------------------------------------------------------------------
_LOCK = threading.Lock()
_STATE = {"running": False, "done": False, "error": None, "log": []}


class _LogWriter:
    """File-like sink: collects builder print() output line by line."""
    def __init__(self):
        self._buf = ""

    def write(self, s):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            with _LOCK:
                _STATE["log"].append(line.rstrip())

    def flush(self):
        pass


def _run_rebuild():
    log = _LogWriter()
    try:
        with redirect_stdout(log), redirect_stderr(log):
            import build as builder          # bundled next to this module
            builder.run_build()
        with _LOCK:
            _STATE["error"] = None
    except Exception:
        with _LOCK:
            _STATE["error"] = traceback.format_exc(limit=4)
    finally:
        with _LOCK:
            _STATE["running"] = False
            _STATE["done"] = True


def start_rebuild() -> bool:
    """Start a background build. Returns False if one is already running."""
    with _LOCK:
        if _STATE["running"]:
            return False
        _STATE.update(running=True, done=False, error=None, log=[])
    threading.Thread(target=_run_rebuild, daemon=True).start()
    return True


# ---------------------------------------------------------------------------
# HTTP handler: static files + JSON API
# ---------------------------------------------------------------------------
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # never let the webview cache an old version of the app
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):  # silence request logging
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/status":
            with _LOCK:
                self._json({"running": _STATE["running"],
                            "done": _STATE["done"],
                            "error": _STATE["error"],
                            "log": _STATE["log"][-30:]})
            return
        super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/upload":
            self._api_upload()
        elif path == "/api/rebuild":
            self._json({"ok": True, "started": start_rebuild()})
        else:
            self._json({"ok": False, "error": "unknown endpoint"}, 404)

    def _api_upload(self):
        name = self.headers.get("X-Filename", "")
        name = os.path.basename(name.replace("\\", "/")).strip()
        if not name.lower().endswith(".pdf") or name.startswith("."):
            self._json({"ok": False, "error": "filename must be a .pdf"}, 400)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0:
            self._json({"ok": False, "error": "empty upload"}, 400)
            return
        if length > MAX_UPLOAD:
            self._json({"ok": False, "error": "file exceeds 100 MB"}, 413)
            return
        data = self.rfile.read(length)
        if not data.startswith(b"%PDF"):
            self._json({"ok": False, "error": "not a PDF file"}, 400)
            return
        MANUALS.mkdir(parents=True, exist_ok=True)
        (MANUALS / name).write_bytes(data)
        count = len(list(MANUALS.glob("*.pdf")))
        self._json({"ok": True, "saved": name, "count": count})


# ---------------------------------------------------------------------------
# Server + window
# ---------------------------------------------------------------------------
def make_server(port=0):
    if not port:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port),
                                 partial(Handler, directory=str(BASE)))
    url = f"http://127.0.0.1:{port}/celica-manual/index.html"
    return server, url


def main():
    port = 0
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            pass

    if "--server-only" in sys.argv:
        server, url = make_server(port)
        print(f"SERVING {url}", flush=True)
        try:
            server.serve_forever()      # until killed
        except KeyboardInterrupt:
            pass
        server.shutdown()
        return

    server, url = make_server(port)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        import webview  # pywebview -> native WebView2 window
        webview.create_window(APP_TITLE, url, width=1500, height=950,
                              min_size=(1000, 650))
        webview.start()          # blocks until the window is closed
    except Exception:
        # Fallback: Edge app-mode window (looks like a native app, no tabs).
        # Dedicated user-data-dir forces a separate process we can wait on.
        profile = os.path.join(os.environ.get("LOCALAPPDATA", "."),
                               "CelicaManualEdge")
        for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
            if os.path.exists(exe):
                subprocess.Popen(
                    [exe, f"--app={url}", f"--user-data-dir={profile}",
                     "--no-first-run"]).wait()
                break
        else:
            import webbrowser
            webbrowser.open(url)
            import time
            time.sleep(86400)   # keep server alive for the browser session
    server.shutdown()


if __name__ == "__main__":
    main()
