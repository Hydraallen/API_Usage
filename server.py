#!/usr/bin/env python3
"""
ZhipuAI Usage Monitor Server
- HTTP server for dashboard and API
- Background scheduler for auto-refresh (every 15 minutes, history/trend only)
- On-demand live quota endpoint so the page shows a fresh balance instantly
- Multi-user: every user has its own history file, status, live-quota cache,
  refresh throttle and in-progress guard. Users are selected with ?user=NAME;
  without it the first configured user is used (backward compatible).
"""

import os
import json
import sys
import time
import threading
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Configuration
# DATA_DIR is shared with zhipu_usage.py through the same env var.
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("PORT", 8080))
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", 15)) * 60  # minutes to seconds
APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
DATA_DIR = Path(os.environ.get("DATA_DIR") or (APP_DIR / "data"))
SCRIPT_PATH = APP_DIR / "zhipu_usage.py"

# Live quota cache TTL (seconds)
LIVE_QUOTA_TTL = int(os.environ.get("LIVE_QUOTA_TTL", 60))

# Minimum spacing between two manual POST /api/refresh triggers (seconds),
# per user. /api/refresh is public and unauthenticated by design, so it needs a
# throttle of its own: without one anybody could drive the upstream query loop
# as fast as they can issue requests. This is distinct from the 409 concurrency
# guard — 429 means "too soon", 409 means "one is running right now".
REFRESH_MIN_INTERVAL = int(os.environ.get("REFRESH_MIN_INTERVAL", 60))
QUOTA_ENDPOINT = "/api/monitor/usage/quota/limit"

# Only these paths may be served from disk. Everything else 404s.
# Previously the handler served the whole /app directory, which meant
# http://host:PORT/server.py handed out the source code (and would have handed
# out anything else that ever landed in /app).
STATIC_WHITELIST = {
    "/dashboard.html": "dashboard.html",
    "/favicon.ico": "favicon.ico",
}
API_PATHS = ("/api/status", "/api/history", "/api/quota/live", "/api/users", "/api/overview")

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
import zhipu_usage  # noqa: E402  (no side effects beyond reading .env)


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
# Per-user state
# ---------------------------------------------------------------------------
class UserState:
    """Everything that used to be a module global, now one instance per user."""

    def __init__(self, cfg):
        self.name = cfg.name
        self.key = cfg.key
        self.history_file = DATA_DIR / cfg.history_name

        self.lock = threading.Lock()
        self.last_update_time = None    # last ATTEMPT (success or failure)
        self.last_success_time = None   # last time the query actually succeeded
        self.last_error = None
        self.consecutive_failures = 0
        self.query_in_progress = False

        self.refresh_gate = threading.Lock()
        self.last_manual_refresh = 0.0  # monotonic timestamp of the last accepted /api/refresh

        self.quota_lock = threading.Lock()
        self.quota_fetch_lock = threading.Lock()  # single-flight for upstream calls
        self.quota_cache = {"fetched_at": None, "data": None, "error": None}

        self.summary_lock = threading.Lock()
        self.summary_cache = (None, None)  # (history mtime, summary dict)


USERS = {}          # name -> UserState, in configuration order
next_round_time = None  # when the scheduler's next collection round starts
CONFIG_ERRORS = ()  # human-readable, key-free
SECRETS = ()        # every key seen in the configuration, for redaction


def configure_users():
    global USERS, CONFIG_ERRORS, SECRETS
    config = zhipu_usage.load_users()
    USERS = {u.name: UserState(u) for u in config.users}
    CONFIG_ERRORS = config.errors
    SECRETS = config.secrets


def default_user():
    return next(iter(USERS.values()), None)


def _redact(text):
    """Strip every configured API key out of anything that may leave the server.

    last_error carries the tail of the collector's stderr, and /api/status is
    public. The collector is not supposed to print a key, but an upstream error
    body echoing one back would slip straight through, so this stays as a
    belt-and-braces filter — over ALL keys, not just the current user's.
    """
    return zhipu_usage.redact(text, SECRETS)


# ---------------------------------------------------------------------------
# Scheduled query (history / trend only — NOT the page's freshness path)
# ---------------------------------------------------------------------------
def run_query(user):
    """Run the usage query script for one user.

    Exit-code contract with zhipu_usage.py:
        0 -> all endpoints succeeded, history written
        2 -> partial success, history written with "partial": true
        1 -> everything failed, NOTHING written to history

    The key is never put on argv (visible in `ps`): the child inherits the
    environment and picks its own key by --user NAME.
    """
    with user.lock:
        if user.query_in_progress:
            log(f"[{user.name}] Query already running, skipping this trigger")
            return False
        user.query_in_progress = True

    started = datetime.now(timezone.utc)
    child_env = dict(os.environ, DATA_DIR=str(DATA_DIR))
    try:
        log(f"[{user.name}] Running usage query...")
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH), "--user", user.name],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(APP_DIR),
            env=child_env,
        )
        rc = result.returncode
        # Redact the whole output BEFORE truncating: cutting first can leave a
        # key prefix that no longer matches the full key.
        tail = _redact((result.stderr or result.stdout or "").strip()).splitlines()
        tail = " | ".join(tail[-5:])[:500]

        with user.lock:
            user.last_update_time = started
            if rc == 0:
                user.last_success_time = started
                user.last_error = None
                user.consecutive_failures = 0
            elif rc == 2:
                # Partial: a record WAS written, but some endpoints failed.
                user.last_success_time = started
                user.last_error = f"partial (rc=2): {tail}"
                user.consecutive_failures = 0
            else:
                user.last_error = f"query failed (rc={rc}): {tail}"
                user.consecutive_failures += 1

        if rc == 0:
            log(f"[{user.name}] Query completed successfully")
        elif rc == 2:
            log(f"[{user.name}] Query completed PARTIALLY: {tail}")
        else:
            log(f"[{user.name}] Query FAILED (rc={rc}): {tail}")
        return rc in (0, 2)

    except subprocess.TimeoutExpired:
        with user.lock:
            user.last_update_time = started
            user.last_error = "query timed out after 60s"
            user.consecutive_failures += 1
        log(f"[{user.name}] Query FAILED: timeout after 60s")
        return False
    except Exception as e:
        msg = _redact(f"query error: {e}")
        with user.lock:
            user.last_update_time = started
            user.last_error = msg
            user.consecutive_failures += 1
        log(f"[{user.name}] Query ERROR: {msg}")
        return False
    finally:
        with user.lock:
            user.query_in_progress = False


def run_all_users():
    """Collect every user one after another (serial: never hammer upstream)."""
    for user in list(USERS.values()):
        run_query(user)


def scheduler():
    """Background scheduler: one round right away, then every REFRESH_INTERVAL.

    The interval counts from the END of a round, and that single "next round"
    time is what every user's next_update reports. Stamping each user with its
    own start + interval made later users in a serial round look due too early.
    """
    global next_round_time
    while True:
        run_all_users()
        next_round_time = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_INTERVAL)
        time.sleep(REFRESH_INTERVAL)


def _iso(dt):
    return dt.isoformat() if dt else None


def get_status(user):
    """Get current status of one user (or a placeholder when none configured)."""
    common = {
        "refresh_interval": REFRESH_INTERVAL,
        "refresh_interval_minutes": REFRESH_INTERVAL // 60,
        "users": list(USERS),
    }
    if user is None:
        return {
            "user": None,
            "last_update": None,
            "last_success_time": None,
            "next_update": None,
            "last_error": "未配置任何 API Key（ZHIPUAI_API_KEYS / ZHIPUAI_API_KEY）",
            "consecutive_failures": 0,
            "healthy": False,
            "query_in_progress": False,
            **common,
        }
    with user.lock:
        return {
            "user": user.name,
            "last_update": _iso(user.last_update_time),
            "last_success_time": _iso(user.last_success_time),
            "next_update": _iso(next_round_time),
            "last_error": user.last_error,
            "consecutive_failures": user.consecutive_failures,
            "healthy": user.consecutive_failures == 0 and user.last_error is None,
            "query_in_progress": user.query_in_progress,
            **common,
        }


# ---------------------------------------------------------------------------
# Live quota (on-demand, 60s TTL per user) — this is what makes the page fresh
# ---------------------------------------------------------------------------
def fetch_live_quota(user):
    """Hit the single read-only quota endpoint. Returns (ok, data, error)."""
    url = f"{zhipu_usage.BASE_URL}{QUOTA_ENDPOINT}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": user.key,  # No "Bearer" prefix!
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
        return False, None, _redact(f"上游请求失败: {e}")

    try:
        payload = json.loads(raw)
    except ValueError:
        payload = raw

    ok, data, error = zhipu_usage.parse_envelope(status, payload, SECRETS)
    return ok, data, _redact(error)


def _quota_payload(ok, cached, fetched_at, data, error, now):
    return {
        "ok": ok,
        "cached": cached,
        "age_seconds": round(now - fetched_at, 1),
        "ttl_seconds": LIVE_QUOTA_TTL,
        "fetched_at": datetime.fromtimestamp(fetched_at, timezone.utc).isoformat(),
        "data": data,
        "error": error,
    }


def _cached_quota(user, now, not_before=None):
    """Cache hit payload, or None. `not_before`: only accept entries fetched after it."""
    with user.quota_lock:
        cache = user.quota_cache
        fetched_at = cache["fetched_at"]
        if fetched_at is None or (now - fetched_at) >= LIVE_QUOTA_TTL:
            return None
        if not_before is not None and fetched_at < not_before:
            return None
        payload = _quota_payload(cache["data"] is not None, True, fetched_at,
                                 cache["data"], cache["error"], now)
    payload["user"] = user.name
    return payload


def get_live_quota(user, force=False):
    """Cached live quota. 60s TTL; cache hits are flagged with cached: true.

    Single-flight per user: on a miss only one thread calls upstream, the rest
    wait on quota_fetch_lock and then take the entry it just stored.
    """
    requested_at = time.time()
    if not force:
        hit = _cached_quota(user, requested_at)
        if hit is not None:
            return hit

    with user.quota_fetch_lock:
        # Re-check: someone may have fetched while we waited. With force, only
        # an entry fetched after this request arrived counts.
        hit = _cached_quota(user, time.time(), not_before=requested_at if force else None)
        if hit is not None:
            return hit
        ok, data, error = fetch_live_quota(user)
        return _store_quota(user, ok, data, error)


def _store_quota(user, ok, data, error):
    fetched = time.time()
    with user.quota_lock:
        user.quota_cache = {
            "fetched_at": fetched,
            "data": data if ok else None,
            "error": None if ok else error,
        }
    payload = _quota_payload(ok, False, fetched, data if ok else None, None if ok else error, fetched)
    payload["user"] = user.name
    return payload


# ---------------------------------------------------------------------------
# Overview (one row per user, built from cheap local state only)
# ---------------------------------------------------------------------------
def _quota_numbers(quota_data):
    """Pull level / 5h % / weekly % out of a quota_limits payload."""
    out = {"level": None, "five_hour_pct": None, "five_hour_reset": None,
           "weekly_pct": None, "weekly_reset": None}
    if not isinstance(quota_data, dict):
        return out
    out["level"] = quota_data.get("level")
    # TOKENS_LIMIT and CREDIT_LIMIT both count; the first entry per window wins.
    for limit in quota_data.get("limits") or []:
        window = zhipu_usage.quota_window(limit)
        prefix = {"5h": "five_hour", "week": "weekly"}.get(window)
        if prefix and out[f"{prefix}_pct"] is None:
            out[f"{prefix}_pct"] = limit.get("percentage")
            out[f"{prefix}_reset"] = limit.get("nextResetTime")
    return out


def _summarize_history(user):
    """Summary of the newest history record, cached on the file's mtime."""
    try:
        mtime = user.history_file.stat().st_mtime
    except OSError:
        return {"record_time": None, "history_error": "暂无历史数据"}

    with user.summary_lock:
        cached_mtime, cached = user.summary_cache
        if cached_mtime == mtime:
            return cached

    try:
        with open(user.history_file, "r", encoding="utf-8") as f:
            records = json.load(f).get("records") or []
    except (OSError, ValueError, AttributeError) as e:
        return {"record_time": None, "history_error": f"历史文件读取失败: {type(e).__name__}"}

    summary = {"record_time": None, "history_error": None if records else "暂无历史数据"}
    if records:
        latest = records[-1]
        results = latest.get("results") or {}
        ql = results.get("quota_limits") or {}
        mu = results.get("model_usage") or {}
        summary["record_time"] = zhipu_usage.to_aware_iso(latest.get("query_time"))
        if ql.get("ok", True):
            summary.update(_quota_numbers(ql.get("data")))
        if mu.get("ok", True):
            total = (mu.get("data") or {}).get("totalUsage") or {}
            summary["tokens_24h"] = total.get("totalTokensUsage")
            summary["calls_24h"] = total.get("totalModelCallCount")

    with user.summary_lock:
        user.summary_cache = (mtime, summary)
    return summary


def get_overview():
    rows = []
    for user in list(USERS.values()):
        row = {"user": user.name, "level": None, "five_hour_pct": None, "five_hour_reset": None,
               "weekly_pct": None, "weekly_reset": None, "tokens_24h": None, "calls_24h": None,
               "quota_source": None}
        hist = _summarize_history(user)
        row.update(hist)
        if row["five_hour_pct"] is not None or row["weekly_pct"] is not None:
            row["quota_source"] = "history"

        # Prefer the live cache when it already holds something newer. This
        # never triggers an upstream call by itself.
        with user.quota_lock:
            live_at, live_data = user.quota_cache["fetched_at"], user.quota_cache["data"]
        if live_data is not None:
            live_dt = datetime.fromtimestamp(live_at, timezone.utc)
            rec = row.get("record_time")
            try:
                rec_dt = datetime.fromisoformat(rec).astimezone(timezone.utc) if rec else None
            except ValueError:
                rec_dt = None
            if rec_dt is None or live_dt > rec_dt:
                row.update(_quota_numbers(live_data))
                row["quota_source"] = "live"
                row["quota_time"] = live_dt.isoformat()

        status = get_status(user)
        row.update({k: status[k] for k in
                    ("healthy", "last_error", "last_success_time", "consecutive_failures",
                     "query_in_progress")})
        rows.append(row)
    return {"users": rows, "default": rows[0]["user"] if rows else None}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class UsageHandler(SimpleHTTPRequestHandler):
    """Custom handler for API endpoints"""

    # Socket timeout per connection: with a threaded server a slow or idle
    # client would otherwise pin a thread indefinitely.
    timeout = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def resolve_user(self, parsed, allow_none=False):
        """?user=NAME -> UserState. Sends the error response and returns None on failure.

        No ?user= means the first configured user (backward compatible).
        """
        names = parse_qs(parsed.query).get("user")
        name = names[0] if names else ""
        if not name:
            user = default_user()
            if user is None and not allow_none:
                self.send_json_response({"error": "未配置任何 API Key"}, status=503)
            return user
        if not zhipu_usage.USER_NAME_RE.match(name):
            self.send_json_response({"error": "user 参数不合法"}, status=400)
            return None
        user = USERS.get(name)
        if user is None:
            self.send_json_response({"error": "用户不存在", "users": list(USERS)}, status=404)
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            # Healthcheck target: with no ?user= it must answer 200 even when
            # nothing is configured.
            has_param = bool(parse_qs(parsed.query).get("user"))
            user = self.resolve_user(parsed, allow_none=True)
            if user is None and has_param:
                return
            self.send_json_response(get_status(user))
        elif path == "/api/users":
            self.send_json_response({
                "users": [{"name": n, "is_default": i == 0} for i, n in enumerate(USERS)],
                "default": next(iter(USERS), None),
                "config_errors": list(CONFIG_ERRORS),
            })
        elif path == "/api/overview":
            self.send_json_response(get_overview())
        elif path == "/api/quota/live":
            user = self.resolve_user(parsed)
            if user is None:
                return
            payload = get_live_quota(user)
            self.send_json_response(payload, status=200 if payload["ok"] else 502)
        elif path == "/api/history":
            user = self.resolve_user(parsed)
            if user is None:
                return
            self.serve_history(user)
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
                or path in API_PATHS:
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if not path.startswith("/api/") else "application/json")
            self.end_headers()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/refresh":
            user = self.resolve_user(parsed)
            if user is None:
                return
            with user.lock:
                busy = user.query_in_progress
            if busy:
                self.send_json_response(
                    {"status": "already_running", **get_status(user)}, status=409
                )
                return

            # Rate limit: at most one manual trigger per REFRESH_MIN_INTERVAL per user.
            now = time.monotonic()
            with user.refresh_gate:
                elapsed = now - user.last_manual_refresh
                if user.last_manual_refresh and elapsed < REFRESH_MIN_INTERVAL:
                    retry_after = int(REFRESH_MIN_INTERVAL - elapsed) + 1
                else:
                    retry_after = 0
                    user.last_manual_refresh = now

            if retry_after:
                self.send_json_response(
                    {
                        "status": "rate_limited",
                        "retry_after_seconds": retry_after,
                        "min_interval_seconds": REFRESH_MIN_INTERVAL,
                        **get_status(user),
                    },
                    status=429,
                    extra_headers={"Retry-After": str(retry_after)},
                )
                return

            threading.Thread(target=run_query, args=(user,), daemon=True).start()
            self.send_json_response({"status": "refresh_triggered", **get_status(user)})
        else:
            self.send_error(404, "Not Found")

    def serve_history(self, user):
        """Return usage history, never crashing on a corrupt file."""
        if not user.history_file.exists():
            self.send_json_response({"user": user.name, "records": [], "error": "No data yet"})
            return
        try:
            with open(user.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.send_json_response(
                {"user": user.name, "records": [], "error": f"历史文件已损坏: {e.msg} (pos {e.pos})"}, status=500
            )
            return
        except OSError as e:
            self.send_json_response(
                # str(OSError) carries the server-side path: send only the type.
                {"user": user.name, "records": [], "error": f"历史文件读取失败: {type(e).__name__}"}, status=500
            )
            return
        if isinstance(data, dict):
            data["user"] = user.name
            # Older records hold naive local times: give every timestamp an
            # explicit offset so the browser never has to guess.
            data["last_updated"] = zhipu_usage.to_aware_iso(data.get("last_updated"))
            for record in data.get("records") or []:
                if isinstance(record, dict):
                    record["query_time"] = zhipu_usage.to_aware_iso(record.get("query_time"))
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

    def send_json_response(self, data, status=200, extra_headers=None):
        """Send JSON response (same-origin only; no CORS wildcard)"""
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[{datetime.now().isoformat()}] {self.address_string()} - {format % args}", flush=True)


def main():
    """Main entry point"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    load_env()
    configure_users()

    print("=" * 60)
    print("🤖 ZhipuAI Usage Monitor Server")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Refresh interval: {REFRESH_INTERVAL // 60} minutes")
    print(f"App directory: {APP_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Live quota TTL: {LIVE_QUOTA_TTL}s")
    print(f"Users: {', '.join(f'{u.name} -> {u.history_file.name}' for u in USERS.values()) or '(none)'}")
    for err in CONFIG_ERRORS:
        print(f"⚠️  {err}")
    print("=" * 60, flush=True)

    # The first round used to run synchronously BEFORE bind(), blocking startup
    # for up to 60 seconds and making the healthcheck flap. The scheduler
    # thread now runs it first, then waits.
    scheduler_thread = threading.Thread(target=scheduler, daemon=True)
    scheduler_thread.start()
    log("Scheduler started")

    # Threading: one slow upstream call (live quota, up to 15s) for one user
    # must not stall every other request. All shared state is per-user locked.
    server = ThreadingHTTPServer(("0.0.0.0", PORT), UsageHandler)
    log(f"Server started at http://0.0.0.0:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped")
        server.shutdown()


if __name__ == "__main__":
    main()
