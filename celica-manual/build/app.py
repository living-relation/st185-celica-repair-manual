"""
ST185 Celica repair-manual desktop app.

Runs a private local web server (in-process, no console, no-cache headers)
and shows the manual app in a native WebView2 window. Packaged with
PyInstaller into CelicaManual.exe — no browser, no downloads, no Adobe.

The server also exposes a small localhost-only JSON API so the app's
"Add manuals" panel can accept new PDFs and rebuild the catalog in place:
    POST /api/upload        raw PDF body + X-Filename header -> stages the
                            file in manuals\\.staging\\ and returns a conflict
                            analysis (page counts, Toyota page-code overlap)
    POST /api/commit        JSON {files:[{name, action}]} with action one of
                            add | abort | overwrite | keep_both -> moves the
                            staged file into manuals\\ (or deletes it)
    POST /api/replace-page  raw ONE-page PDF body + X-Target + X-Page
                            headers -> swaps that page inside the manual
    POST /api/rebuild       runs the catalog builder in a background thread
    GET  /api/status        {running, done, error, log: [...last lines...]}

CLI:  app.py [--server-only] [--port N]
    --server-only   start the server, print "SERVING <url>", no window
                    (used for headless testing / running under a browser)
"""
import json
import os
import re
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
CONTENT_OVERLAP = 0.30              # >=30% shared page codes -> conflict


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
STAGING = MANUALS / ".staging"      # not matched by the builder's *.pdf glob
THUMBS = BASE / "celica-manual" / "thumbs"

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
# Upload staging + conflict analysis
# ---------------------------------------------------------------------------
_SCAN_CACHE = {}        # filename -> ((mtime_ns, size), page_count, set(codes))
_CODE_NUM = re.compile(r"^([A-Z]{2})-(\d+)")


def _pdf_scan(path):
    """(page_count, [detected Toyota footer codes]) for one PDF, using the
    builder's CODE_LINE regex and text normalization (shared, not duplicated)."""
    import fitz
    import build as builder
    doc = fitz.open(path)
    codes = []
    for pg in doc:
        last = None
        for ln in builder.norm(pg.get_text("text")).splitlines():
            m = builder.CODE_LINE.match(ln.strip())
            if m:
                last = f"{m.group(1)}-{m.group(2)}"
        if last:
            codes.append(last)
    n = doc.page_count
    doc.close()
    return n, codes


def _existing_pdfs():
    """Scan the CURRENT manuals folder (correct even before a rebuild).
    Cached per file by (mtime, size)."""
    out = {}
    for p in sorted(MANUALS.glob("*.pdf")):
        st = p.stat()
        key = (st.st_mtime_ns, st.st_size)
        ent = _SCAN_CACHE.get(p.name)
        if not ent or ent[0] != key:
            pages, codes = _pdf_scan(p)
            ent = (key, pages, set(codes))
            _SCAN_CACHE[p.name] = ent
        out[p.name] = ent
    return out


def _code_range(codes):
    def k(c):
        m = _CODE_NUM.match(c)
        return (m.group(1), int(m.group(2))) if m else (c, 0)
    s = sorted(set(codes), key=k)
    if not s:
        return ""
    return s[0] if len(s) == 1 else s[0] + "–" + s[-1]


def _analyze(staged_path, name):
    """Conflict analysis of one staged file against the current manuals\\.
    Returns (info, conflict|None)."""
    i_pages, i_codes = _pdf_scan(staged_path)
    inc = set(i_codes)
    existing = _existing_pdfs()

    target = why = None
    if name in existing:
        target, why = name, "filename"
    elif inc:
        best = None
        for ename, (_k, _p, ecodes) in existing.items():
            ov = len(inc & ecodes)
            if ov and ov >= CONTENT_OVERLAP * len(inc) \
               and (best is None or ov > best[1]):
                best = (ename, ov)
        if best:
            target, why = best[0], "content"

    info = {"pages": i_pages, "codes": len(inc), "range": _code_range(inc)}
    if not target:
        return info, None

    _k, e_pages, e_codes = existing[target]
    overlap = len(inc & e_codes)
    # pages that would disappear if the staged file replaced the existing one
    lost = max(0, e_pages - i_pages,
               len(e_codes - inc) if e_codes else 0)
    if i_pages != e_pages:
        verdict = "more_complete" if i_pages > e_pages else "less_complete"
    elif len(inc) != len(e_codes):
        verdict = "more_complete" if len(inc) > len(e_codes) \
            else "less_complete"
    else:
        verdict = "similar"
    return info, {
        "type": why, "existing": target,
        "incoming_pages": i_pages, "incoming_codes": len(inc),
        "incoming_range": _code_range(inc),
        "existing_pages": e_pages, "existing_codes": len(e_codes),
        "existing_range": _code_range(e_codes),
        "overlap": overlap, "verdict": verdict,
        "pages_lost_if_overwrite": lost,
    }


def _purge_previews(stem, first_page=True):
    """Remove stale generated previews so the next rebuild re-renders them."""
    if first_page:
        (THUMBS / (stem + ".png")).unlink(missing_ok=True)
    pages_dir = THUMBS / "pages"
    if pages_dir.is_dir():
        for p in pages_dir.iterdir():
            if p.name.startswith(stem + "_p") and p.suffix == ".png":
                p.unlink()


def _suffixed(name):
    """Non-colliding Name_v2.pdf / Name_v3.pdf ... in manuals\\."""
    stem, ext = os.path.splitext(name)
    n = 2
    while (MANUALS / f"{stem}_v{n}{ext}").exists():
        n += 1
    return f"{stem}_v{n}{ext}"


def _clean_name(raw):
    name = os.path.basename((raw or "").replace("\\", "/")).strip()
    if not name.lower().endswith(".pdf") or name.startswith("."):
        return None
    return name


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

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_UPLOAD:
            return None
        return self.rfile.read(length)

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
        try:
            if path == "/api/upload":
                self._api_upload()
            elif path == "/api/commit":
                self._api_commit()
            elif path == "/api/replace-page":
                self._api_replace_page()
            elif path == "/api/rebuild":
                self._json({"ok": True, "started": start_rebuild()})
            else:
                self._json({"ok": False, "error": "unknown endpoint"}, 404)
        except Exception:
            self._json({"ok": False,
                        "error": traceback.format_exc(limit=3)}, 500)

    def _api_upload(self):
        """Phase A: save to manuals\\.staging\\ and analyze for conflicts."""
        name = _clean_name(self.headers.get("X-Filename", ""))
        if not name:
            self._json({"ok": False, "error": "filename must be a .pdf"}, 400)
            return
        data = self._read_body()
        if data is None:
            self._json({"ok": False,
                        "error": "empty upload or file exceeds 100 MB"}, 400)
            return
        if not data.startswith(b"%PDF"):
            self._json({"ok": False, "error": "not a PDF file"}, 400)
            return
        STAGING.mkdir(parents=True, exist_ok=True)
        staged = STAGING / name
        staged.write_bytes(data)
        try:
            info, conflict = _analyze(staged, name)
        except Exception as e:
            staged.unlink(missing_ok=True)
            self._json({"ok": False, "error": f"could not read PDF: {e}"}, 400)
            return
        self._json({"ok": True, "staged": name, "pages": info["pages"],
                    "codes": info["codes"], "range": info["range"],
                    "conflict": conflict})

    def _api_commit(self):
        """Phase B: apply per-file decisions to the staged uploads."""
        raw = self._read_body()
        try:
            req = json.loads(raw or b"")
        except (ValueError, TypeError):
            self._json({"ok": False, "error": "bad JSON body"}, 400)
            return
        results = []
        for item in req.get("files", []):
            name = _clean_name(item.get("name", ""))
            action = item.get("action", "add")
            res = {"name": name, "action": action, "ok": False}
            sp = STAGING / name if name else None
            if not name or not sp.is_file():
                res["error"] = "file is not staged"
            elif action == "abort":
                sp.unlink()
                res.update(ok=True, final=None)
            elif action == "overwrite":
                _purge_previews(Path(name).stem)
                os.replace(sp, MANUALS / name)
                res.update(ok=True, final=name)
            elif action == "keep_both":
                final = _suffixed(name)
                os.replace(sp, MANUALS / final)
                res.update(ok=True, final=final)
            elif action == "add":
                if (MANUALS / name).exists():
                    res["error"] = "file already exists — resolve the conflict"
                else:
                    os.replace(sp, MANUALS / name)
                    res.update(ok=True, final=name)
            else:
                res["error"] = "unknown action"
            results.append(res)
        count = len(list(MANUALS.glob("*.pdf")))
        self._json({"ok": True, "results": results, "count": count})

    def _api_replace_page(self):
        """Swap one page of an existing manual with an uploaded 1-page PDF."""
        import fitz
        target = _clean_name(self.headers.get("X-Target", ""))
        try:
            page = int(self.headers.get("X-Page", "0"))
        except ValueError:
            page = 0
        if not target or not (MANUALS / target).is_file():
            self._json({"ok": False, "error": "manual not found"}, 404)
            return
        data = self._read_body()
        if data is None or not data.startswith(b"%PDF"):
            self._json({"ok": False, "error": "not a PDF file"}, 400)
            return
        repl = fitz.open(stream=data, filetype="pdf")
        if repl.page_count != 1:
            n = repl.page_count
            repl.close()
            self._json({"ok": False,
                        "error": f"replacement must be a single-page PDF "
                                 f"(yours has {n} pages)"}, 400)
            return
        tpath = MANUALS / target
        doc = fitz.open(tpath)
        old = doc.page_count
        if not 1 <= page <= old:
            doc.close()
            repl.close()
            self._json({"ok": False,
                        "error": f"page must be 1..{old}"}, 400)
            return
        doc.delete_page(page - 1)
        doc.insert_pdf(repl, from_page=0, to_page=0, start_at=page - 1)
        new = doc.page_count
        STAGING.mkdir(parents=True, exist_ok=True)
        tmp = STAGING / (target + ".tmp")
        doc.save(str(tmp))
        doc.close()
        repl.close()
        # atomic swap, keeping a .bak of the original until success
        bak = MANUALS / (target + ".bak")
        os.replace(tpath, bak)
        try:
            os.replace(tmp, tpath)
        except Exception:
            os.replace(bak, tpath)          # roll back
            raise
        bak.unlink(missing_ok=True)
        _purge_previews(Path(target).stem, first_page=(page == 1))
        self._json({"ok": new == old, "file": target, "page": page,
                    "pages": new,
                    **({} if new == old else
                       {"error": f"page count changed {old} -> {new}"})})


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
