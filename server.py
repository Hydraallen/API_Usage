#!/usr/bin/env python3
"""
ZhipuAI Usage Monitor Server
- HTTP server for dashboard and API
- Background scheduler for auto-refresh (every 15 minutes, history/trend only)
- On-demand live quota endpoint so the page shows a fresh balance instantly
"""

import os
import json
import time
import threading
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Configuration
# DATA_DIR is shared with zhipu_usage.py through the same env var.
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("PORT", 8080))
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", 15)) * 60  # minutes to seconds
APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
DATA_DIR = Path(os.environ.get("DATA_DIR") or (APP_DIR / "data"))
SCRIPT_PATH = APP_DIR / "zhipu_usage.py"
HISTORY_FILE = DATA_DIR / "usage_history.json"

# Live quota cache TTL (seconds)
LIVE_QUOTA_TTL = int(os.environ.get("LIVE_QUOTA_TTL", 60))
QUOTA_ENDPOINT = "/api/monitor/usage/quota/limit"

# Only these paths may be served from disk. Everything else 404s.
# Previously the handler served the whole /app directory, which meant
# http://host:PORT/server.py handed out the source code (and would have handed
# out anything else that ever landed in /app).
STATIC_WHITELIST = {
    "/dashboard.html": "dashboard.html",
    "/favicon.ico": "favicon.ico",
}

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
last_update_time = None        # last ATTEMPT (success or failure)
last_success_time = None       # last time the query actually succeeded
next_update_time = None
last_error = None
consecutive_failures = 0
query_in_progress = False
update_lock = threading.Lock()

# Live quota cache
_quota_cache = {"fetched_at": None, "data": None, "error": None}
_quota_lock = threading.Lock()


def load_env():
    """Load environment variables from .env file"""
    env_file = DATA_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Scheduled query (history / trend only — NOT the page's freshness path)
# ---------------------------------------------------------------------------
def run_query():
    """Run the usage query script.

    Exit-code contract with zhipu_usage.py:
        0 -> all endpoints succeeded, history written
        2 -> partial success, history written with "partial": true
        1 -> everything failed, NOTHING written to history
    """
    global last_update_time, next_update_time, last_success_time
    global last_error, consecutive_failures, query_in_progress

    with update_lock:
        if query_in_progress:
            log("Query already running, skipping this trigger")
            return False
        query_in_progress = True

    started = datetime.now(timezone.utc)
    try:
        log("Running usage query...")
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(APP_DIR),
        )
        rc = result.returncode
        tail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = " | ".join(tail[-5:])[:500]

        with update_lock:
            last_update_time = started
            next_update_time = started + timedelta(seconds=REFRESH_INTERVAL)
            if rc == 0:
                last_success_time = started
                last_error = None
                consecutive_failures = 0
            elif rc == 2:
                # Partial: a record WAS written, but some endpoints failed.
                last_success_time = started
                last_error = f"partial (rc=2): {tail}"
                consecutive_failures = 0
            else:
                last_error = f"query failed (rc={rc}): {tail}"
                consecutive_failures += 1

        if rc == 0:
            log("Query completed successfully")
        elif rc == 2:
            log(f"Query completed PARTIALLY: {tail}")
        else:
            log(f"Query FAILED (rc={rc}): {tail}")
        return rc in (0, 2)

    except subprocess.TimeoutExpired:
        with update_lock:
            last_update_time = started
            next_update_time = started + timedelta(seconds=REFRESH_INTERVAL)
            last_error = "query timed out after 60s"
            consecutive_failures += 1
        log("Query FAILED: timeout after 60s")
        return False
    except Exception as e:
        with update_lock:
            last_update_time = started
            next_update_time = started + timedelta(seconds=REFRESH_INTERVAL)
            last_error = f"query error: {e}"
            consecutive_failures += 1
        log(f"Query ERROR: {e}")
        return False
    finally:
        with update_lock:
            query_in_progress = False


def scheduler():
    """Background scheduler for auto-refresh (15 min by default)"""
    while True:
        time.sleep(REFRESH_INTERVAL)
        run_query()


def get_status():
    """Get current status"""
    with update_lock:
        return {
            "last_update": last_update_time.isoformat() if last_update_time else None,
            "last_success_time": last_success_time.isoformat() if last_success_time else None,
            "next_update": next_update_time.isoformat() if next_update_time else None,
            "last_error": last_error,
            "consecutive_failures": consecutive_failures,
            "healthy": consecutive_failures == 0 and last_error is None,
            "query_in_progress": query_in_progress,
            "refresh_interval": REFRESH_INTERVAL,
            "refresh_interval_minutes": REFRESH_INTERVAL // 60,
        }


# ---------------------------------------------------------------------------
# Live quota (on-demand, 60s TTL) — this is what makes the page fresh
# ---------------------------------------------------------------------------
_zhipu_mod = None
_zhipu_mod_error = None


def _query_helpers():
    """Lazily import zhipu_usage for BASE_URL / API_KEY / parse_envelope.

    Imported lazily on purpose: the module exits at import time when
    ZHIPUAI_API_KEY is missing, and we want that to become a JSON error on one
    endpoint instead of killing the whole server at boot.
    """
    global _zhipu_mod, _zhipu_mod_error
    if _zhipu_mod is not None or _zhipu_mod_error is not None:
        return _zhipu_mod, _zhipu_mod_error
    try:
        import importlib
        import sys
        if str(APP_DIR) not in sys.path:
            sys.path.insert(0, str(APP_DIR))
        _zhipu_mod = importlib.import_module("zhipu_usage")
    except SystemExit:
        _zhipu_mod_error = "ZHIPUAI_API_KEY 未配置 (.env 缺失或为空)"
    except Exception as e:
        _zhipu_mod_error = f"无法加载查询模块: {e}"
    return _zhipu_mod, _zhipu_mod_error


def fetch_live_quota():
    """Hit the single read-only quota endpoint. Returns (ok, data, error)."""
    mod, mod_err = _query_helpers()
    if mod is None:
        return False, None, mod_err

    url = f"{mod.BASE_URL}{QUOTA_ENDPOINT}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": mod.API_KEY,  # No "Bearer" prefix!
            "Accept-Language": "en-US,en",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace") if e.fp else ""
        status = e.code
    except Exception as e:
        return False, None, f"上游请求失败: {e}"

    try:
        payload = json.loads(raw)
    except ValueError:
        payload = raw

    return mod.parse_envelope(status, payload)


def get_live_quota(force=False):
    """Cached live quota. 60s TTL; cache hits are flagged with cached: true."""
    now = time.time()
    with _quota_lock:
        fetched_at = _quota_cache["fetched_at"]
        if not force and fetched_at is not None and (now - fetched_at) < LIVE_QUOTA_TTL:
            age = now - fetched_at
            if _quota_cache["data"] is not None:
                return {
                    "ok": True,
                    "cached": True,
                    "age_seconds": round(age, 1),
                    "ttl_seconds": LIVE_QUOTA_TTL,
                    "fetched_at": datetime.fromtimestamp(fetched_at, timezone.utc).isoformat(),
                    "data": _quota_cache["data"],
                    "error": None,
                }
            return {
                "ok": False,
                "cached": True,
                "age_seconds": round(age, 1),
                "ttl_seconds": LIVE_QUOTA_TTL,
                "fetched_at": datetime.fromtimestamp(fetched_at, timezone.utc).isoformat(),
                "data": None,
                "error": _quota_cache["error"],
            }

    ok, data, error = fetch_live_quota()
    fetched = time.time()
    with _quota_lock:
        _quota_cache["fetched_at"] = fetched
        _quota_cache["data"] = data if ok else None
        _quota_cache["error"] = None if ok else error

    return {
        "ok": ok,
        "cached": False,
        "age_seconds": 0.0,
        "ttl_seconds": LIVE_QUOTA_TTL,
        "fetched_at": datetime.fromtimestamp(fetched, timezone.utc).isoformat(),
        "data": data if ok else None,
        "error": None if ok else error,
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class UsageHandler(SimpleHTTPRequestHandler):
    """Custom handler for API endpoints"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self.send_json_response(get_status())
        elif path == "/api/quota/live":
            payload = get_live_quota()
            self.send_json_response(payload, status=200 if payload["ok"] else 502)
        elif path == "/api/history":
            self.serve_history()
        elif path in ("/", "/index.html", "/dashboard.html"):
            self.serve_static("dashboard.html")
        elif path in STATIC_WHITELIST:
            self.serve_static(STATIC_WHITELIST[path])
        else:
            self.send_error(404, "Not Found")

    def do_HEAD(self):
        # Without this override the inherited handler would still expose the
        # whole /app directory over HEAD.
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html", "/dashboard.html") or path in STATIC_WHITELIST \
                or path in ("/api/status", "/api/history", "/api/quota/live"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if not path.startswith("/api/") else "application/json")
            self.end_headers()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/refresh":
            with update_lock:
                busy = query_in_progress
            if busy:
                self.send_json_response(
                    {"status": "already_running", **get_status()}, status=409
                )
                return
            threading.Thread(target=run_query, daemon=True).start()
            self.send_json_response({"status": "refresh_triggered", **get_status()})
        else:
            self.send_error(404, "Not Found")

    def serve_history(self):
        """Return usage history, never crashing on a corrupt file."""
        if not HISTORY_FILE.exists():
            self.send_json_response({"records": [], "error": "No data yet"})
            return
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.send_json_response(
                {"records": [], "error": f"历史文件已损坏: {e}"}, status=500
            )
            return
        except OSError as e:
            self.send_json_response(
                {"records": [], "error": f"历史文件读取失败: {e}"}, status=500
            )
            return
        self.send_json_response(data)

    def serve_static(self, filename):
        """Serve one whitelisted file from APP_DIR."""
        target = APP_DIR / filename
        if not target.is_file():
            self.send_error(404, "Not Found")
            return
        ctype = self.guess_type(str(target))
        try:
            body = target.read_bytes()
        except OSError:
            self.send_error(404, "Not Found")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_json_response(self, data, status=200):
        """Send JSON response (same-origin only; no CORS wildcard)"""
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[{datetime.now().isoformat()}] {self.address_string()} - {format % args}", flush=True)


def main():
    """Main entry point"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    load_env()

    print("=" * 60)
    print("🤖 ZhipuAI Usage Monitor Server")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Refresh interval: {REFRESH_INTERVAL // 60} minutes")
    print(f"App directory: {APP_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Live quota TTL: {LIVE_QUOTA_TTL}s")
    print("=" * 60, flush=True)

    # The first query used to run synchronously BEFORE bind(), blocking startup
    # for up to 60 seconds and making the healthcheck flap. Now it is a thread.
    threading.Thread(target=run_query, daemon=True).start()

    scheduler_thread = threading.Thread(target=scheduler, daemon=True)
    scheduler_thread.start()
    log("Scheduler started")

    server = HTTPServer(("0.0.0.0", PORT), UsageHandler)
    log(f"Server started at http://0.0.0.0:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped")
        server.shutdown()


if __name__ == "__main__":
    main()
