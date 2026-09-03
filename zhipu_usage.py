#!/usr/bin/env python3
"""
ZhipuAI Coding Plan Usage Query Script
Query account balance, usage statistics, and quota information

API Endpoints discovered from:
- https://github.com/guyinwonder168/opencode-glm-quota
- https://github.com/lgcyaxi/oh-my-claude

Author: E.D.I.T.H.
Created: 2026-03-04
Updated: 2026-09-03 - Zero third-party dependencies (stdlib urllib only),
                      envelope-shape success detection, uniform {ok,payload,error}
                      contract, atomic history writes, non-zero exit on failure,
                      removed the quota-consuming chat/completions probe.
"""

import os
import sys
import json
import socket
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment / paths
#
# DATA_DIR is the single knob shared with server.py. Precedence:
#   1. $DATA_DIR (explicit, wins everywhere)
#   2. /app/data when running inside Docker
#   3. the directory this script lives in (local runs)
#
# Docker detection: the sentinel file is /.dockerenv at the filesystem ROOT
# (it used to be spelled "/app/.dockerenv", which never exists).
# ---------------------------------------------------------------------------
IN_DOCKER = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_ENV") == "true"
_DATA_DIR_ENV = os.environ.get("DATA_DIR", "").strip()
if _DATA_DIR_ENV:
    DATA_DIR = Path(_DATA_DIR_ENV)
elif IN_DOCKER:
    DATA_DIR = Path("/app/data")
else:
    DATA_DIR = Path(__file__).parent


# Load environment variables from .env file
def load_env():
    """Load environment variables from .env file"""
    env_paths = [
        DATA_DIR / ".env",
        Path(__file__).parent / ".env",
        Path("/app/.env"),
    ]

    for env_file in env_paths:
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
            return

load_env()

# Configuration
API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
if not API_KEY:
    print("❌ 错误: 未找到 ZHIPUAI_API_KEY")
    print("   请创建 .env 文件并设置 ZHIPUAI_API_KEY=your_api_key")
    print("   或设置环境变量: export ZHIPUAI_API_KEY=your_api_key")
    sys.exit(1)

BASE_URL = "https://open.bigmodel.cn"  # CN platform


def api_key_preview() -> str:
    """Masked key for logs and on-disk records.

    Deliberately short: 6 leading + 4 trailing characters. The old 20+10 form
    revealed 30 characters of a 49-character key — far more than a human needs
    to tell two keys apart, and far more than belongs in a persisted file.
    """
    if not API_KEY:
        return ""
    if len(API_KEY) <= 10:
        return "*" * len(API_KEY)
    return f"{API_KEY[:6]}...{API_KEY[-4:]}"


# ---------------------------------------------------------------------------
# Token cost estimates (per million tokens, in CNY).
#
# ⚠️ A price of None means "we do not know the official price".
#    It is NEVER treated as 0 and NEVER borrowed from a similarly-named model —
#    the UI prints 「价格未知」instead. Fill a real number in only when it has
#    been confirmed against the vendor's published price list.
# ---------------------------------------------------------------------------
MODEL_PRICING: Dict[str, Dict[str, Optional[float]]] = {
    "glm-5": {"input": 4, "output": 18},
    "glm-5-code": {"input": 6, "output": 28},
    # GLM-5.3 family: this account's actual working models. Official per-token
    # pricing has not been verified, so it stays explicitly unknown.
    "glm-5.3": {"input": None, "output": None},
    "glm-5.3-flash": {"input": None, "output": None},
    "glm-4.7": {"input": 2, "output": 8},
    "glm-4.7-flashx": {"input": 0.5, "output": 3},
    "glm-4.7-flash": {"input": 0, "output": 0},  # Free
    "glm-4.5-air": {"input": 0.8, "output": 2},
    "glm-4-plus": {"input": 5, "output": 2.5},
    "glm-4-air": {"input": 0.5, "output": 0.25},
    "glm-4-flashx": {"input": 0.1, "output": 0.05},
    "glm-4-long": {"input": 1, "output": 0.5},
}

UNKNOWN_PRICING: Dict[str, Optional[float]] = {"input": None, "output": None}


def lookup_pricing(model_id: str) -> Dict[str, Optional[float]]:
    """Case-insensitive pricing lookup. Unknown model -> unknown price."""
    return MODEL_PRICING.get((model_id or "").lower(), UNKNOWN_PRICING)


def format_pricing(model_id: str) -> str:
    """Human readable price line, or an explicit 'unknown' marker."""
    pricing = lookup_pricing(model_id)
    if pricing.get("input") is None or pricing.get("output") is None:
        return "价格未知"
    return f"¥{pricing['input']}/M 输入, ¥{pricing['output']}/M 输出"


# ---------------------------------------------------------------------------
# Response envelope handling
#
# The upstream serves TWO different envelope shapes and we must not hardcode
# which endpoint uses which:
#
#   A) monitor style : {"code":200,"msg":"...","data":{...},"success":true}
#   B) OpenAI style  : {"object":"list","data":[...]}          <- NO "success"
#
# The old code required resp_data["success"] unconditionally, so every call to
# /api/paas/v4/models was judged a failure even on a perfectly good HTTP 200.
# parse_envelope() decides by SHAPE, once, for every endpoint.
# ---------------------------------------------------------------------------
def parse_envelope(status_code: Optional[int], payload: Any) -> Tuple[bool, Any, Optional[str]]:
    """Return (ok, data, error) for any upstream response body."""
    if status_code != 200:
        detail = ""
        if isinstance(payload, dict):
            detail = str(payload.get("msg") or payload.get("message") or payload.get("error") or "")
        elif isinstance(payload, str):
            detail = payload[:200]
        return False, None, f"HTTP {status_code}{': ' + detail if detail else ''}"

    if not isinstance(payload, dict):
        return False, None, "响应不是 JSON 对象"

    # Explicit error object (some gateway errors come back with HTTP 200)
    err = payload.get("error")
    if isinstance(err, dict) and err:
        return False, None, str(err.get("message") or err)

    # Shape A: an explicit success flag exists -> trust it
    if "success" in payload:
        if payload.get("success"):
            return True, payload.get("data"), None
        return False, None, str(payload.get("msg") or payload.get("message") or "上游返回 success=false")

    # Shape B: no success flag, but a data field -> treat HTTP 200 as success
    if "data" in payload:
        return True, payload.get("data"), None

    return False, None, "无法识别的响应信封"


def ok_result(payload: Any) -> Dict[str, Any]:
    return {"ok": True, "payload": payload, "error": None}


def err_result(error: str) -> Dict[str, Any]:
    return {"ok": False, "payload": None, "error": error}


def _http_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Any] = None,
    timeout: int = 30,
) -> Tuple[Optional[int], Any, Optional[str]]:
    """Single choke point for every outbound HTTP call (standard library only).

    Returns (status_code, parsed_json, error). Exactly one of `parsed_json` /
    `error` is meaningful:

      * transport failure (DNS, refused, timeout) -> (None, None, "...")
      * body that is not JSON                     -> (status, None, "... 原文前200字符 ...")
      * anything else                             -> (status, <parsed>, None)

    A non-2xx status is NOT a transport failure: urllib raises HTTPError for it,
    but the response body normally carries the vendor's real error detail, so we
    read it back and hand the parsed body to parse_envelope like any other
    response. Dropping that body is how "HTTP 401" loses "invalid api key".
    """
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # Non-2xx. Keep the body — the error detail lives in it.
        status = e.code
        try:
            raw = e.read().decode("utf-8", "replace") if e.fp is not None else ""
        except Exception:
            raw = ""
    except socket.timeout:
        return None, None, f"请求超时 (>{timeout}s)"
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, socket.timeout):
            return None, None, f"请求超时 (>{timeout}s)"
        return None, None, f"网络错误: {reason}"
    except OSError as e:
        return None, None, f"网络错误: {e}"

    if not raw.strip():
        return status, None, f"HTTP {status}: 响应体为空"

    try:
        return status, json.loads(raw), None
    except json.JSONDecodeError as e:
        # Never a bare `except:` — we want to know it was a decode problem, and
        # we keep the head of the raw text because that is what makes a
        # gateway/HTML error page identifiable at a glance.
        snippet = raw[:200]
        return status, None, f"HTTP {status}: 响应不是合法 JSON ({e.msg}); 原文前200字符: {snippet!r}"


def make_request(endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict[str, Any]:
    """Make authenticated request to ZhipuAI API.

    Always returns the uniform {ok, payload, error} contract; `payload` is the
    UNWRAPPED inner data (envelope already peeled off).

    Note: Authorization header does NOT use "Bearer" prefix!
    """
    method = method.upper()
    url = f"{BASE_URL}{endpoint}"
    body = None
    if method == "GET":
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
    else:
        body = params

    headers = {
        "Authorization": API_KEY,  # No "Bearer" prefix!
        "Accept-Language": "en-US,en",
        "Content-Type": "application/json",
    }

    status, payload, error = _http_request(method, url, headers, body=body)
    if error is not None:
        return err_result(f"{endpoint} -> {error}")

    ok, data, envelope_error = parse_envelope(status, payload)
    if ok:
        return ok_result(data)
    return err_result(f"{endpoint} -> {envelope_error}")


def get_time_window() -> tuple:
    """Get 24-hour rolling window in required format"""
    now = datetime.now()
    start = now - timedelta(hours=24)
    return start.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp (ms) to readable string"""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def format_duration(ms: int) -> str:
    """Format duration in ms to human readable string"""
    seconds = ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours >= 24:
        days = hours // 24
        remaining_hours = hours % 24
        return f"{days}天 {remaining_hours}小时"
    return f"{hours}小时 {minutes}分钟"


def print_progress_bar(percentage: float, width: int = 40) -> str:
    """Create ASCII progress bar"""
    filled = int(width * percentage / 100)
    empty = width - filled
    return "[" + "#" * filled + "-" * empty + f"] {percentage:.1f}%"


def query_quota_limits() -> Dict[str, Any]:
    """Query current quota limits -> {ok, payload, error}"""
    print("\n" + "=" * 70)
    print("📊 CODING PLAN 配额限制 (QUOTA LIMITS)")
    print("=" * 70)

    result = make_request("/api/monitor/usage/quota/limit")

    if not result["ok"]:
        print(f"❌ 查询失败: {result['error']}")
        return result

    data = result["payload"] if isinstance(result["payload"], dict) else {}
    limits = data.get("limits", [])
    level = data.get("level", "unknown")

    print(f"\n🏷️  账户等级: {str(level).upper()}")
    print()

    for limit in limits:
        limit_type = limit.get("type", "Unknown")
        unit = limit.get("unit", 0)
        number = limit.get("number", 0)
        percentage = limit.get("percentage", 0)
        next_reset = limit.get("nextResetTime", 0)

        if limit_type == "TOKENS_LIMIT":
            if unit == 3 and number == 5:
                print("⏱️  5小时 Token 限额:")
            elif unit == 6 and number == 1:
                print("📅 周度 Token 限额:")
            else:
                print(f"📦 Token 限额 (Unit {unit}, {number}):")

            print(f"   {print_progress_bar(percentage)}")
            if next_reset:
                print(f"   重置时间: {format_timestamp(next_reset)} "
                      f"({format_duration(next_reset - int(datetime.now().timestamp() * 1000))} 后)")
            print()

        elif limit_type == "TIME_LIMIT":
            print("🔧 MCP 工具使用限额 (月度):")
            print(f"   {print_progress_bar(percentage)}")
            print(f"   已用: {limit.get('usage', 0):,} / "
                  f"{limit.get('currentValue', 0) + limit.get('remaining', 0):,}")
            print(f"   剩余: {limit.get('remaining', 0):,}")
            if next_reset:
                print(f"   重置时间: {format_timestamp(next_reset)}")

            usage_details = limit.get("usageDetails", [])
            if usage_details:
                print("\n   📈 工具使用详情:")
                for detail in usage_details:
                    model = detail.get("modelCode", "unknown")
                    usage = detail.get("usage", 0)
                    print(f"      • {model}: {usage:,}")
            print()

    return result


def query_model_usage() -> Dict[str, Any]:
    """Query model usage statistics for 24-hour rolling window"""
    print("\n" + "=" * 70)
    print("🤖 模型使用统计 (MODEL USAGE - 24h)")
    print("=" * 70)

    start_time, end_time = get_time_window()
    params = {"startTime": start_time, "endTime": end_time}

    result = make_request("/api/monitor/usage/model-usage", params=params)

    if not result["ok"]:
        print(f"❌ 查询失败: {result['error']}")
        return result

    data = result["payload"] if isinstance(result["payload"], dict) else {}
    total_usage = data.get("totalUsage", {})

    total_calls = total_usage.get("totalModelCallCount", 0)
    total_tokens = total_usage.get("totalTokensUsage", 0)

    print("\n📊 总计 (24小时):")
    print(f"   📞 调用次数: {total_calls:,}")
    print(f"   🎫 Token 使用: {total_tokens:,}")
    print(f"\n📅 时间范围: {start_time} → {end_time}")

    x_time = data.get("x_time", [])
    tokens_usage = data.get("tokensUsage", [])
    call_counts = data.get("modelCallCount", [])

    if x_time:
        print("\n📈 最近12小时使用趋势:")
        recent_count = min(12, len(x_time))
        for i in range(-recent_count, 0):
            time_slot = x_time[i]
            tokens = tokens_usage[i] if i < len(tokens_usage) and tokens_usage[i] else 0
            calls = call_counts[i] if i < len(call_counts) and call_counts[i] else 0
            print(f"   {time_slot}: {tokens:>12,} tokens, {calls:>4} calls")

    return result


def query_tool_usage() -> Dict[str, Any]:
    """Query MCP tool usage statistics for 24-hour rolling window"""
    print("\n" + "=" * 70)
    print("🔧 工具使用统计 (TOOL/MCP USAGE - 24h)")
    print("=" * 70)

    start_time, end_time = get_time_window()
    params = {"startTime": start_time, "endTime": end_time}

    result = make_request("/api/monitor/usage/tool-usage", params=params)

    if not result["ok"]:
        print(f"❌ 查询失败: {result['error']}")
        return result

    data = result["payload"] if isinstance(result["payload"], dict) else {}
    total_usage = data.get("totalUsage", {})

    print("\n📊 工具使用总计 (24小时):")
    print(f"   🔍 网络搜索: {total_usage.get('totalNetworkSearchCount', 0):,}")
    print(f"   📖 网页阅读: {total_usage.get('totalWebReadMcpCount', 0):,}")
    print(f"   📚 ZRead: {total_usage.get('totalZreadMcpCount', 0):,}")
    print(f"   📁 总计: {total_usage.get('totalSearchMcpCount', 0):,}")

    tool_details = total_usage.get("toolDetails", [])
    if tool_details:
        print("\n📈 工具详情:")
        for detail in tool_details:
            model = detail.get("modelName", "unknown")
            count = detail.get("totalUsageCount", 0)
            print(f"      • {model}: {count:,}")

    return result


def query_available_models() -> Dict[str, Any]:
    """Query available models.

    This endpoint answers with the OpenAI-style envelope
    {"object":"list","data":[...]} and carries NO "success" key — the reason
    it used to be reported as 100/100 failures.
    """
    print("\n" + "=" * 70)
    print("🤖 可用模型 (AVAILABLE MODELS)")
    print("=" * 70)

    result = make_request("/api/paas/v4/models")

    if not result["ok"]:
        print(f"❌ 查询失败: {result['error']}")
        return result

    models = result["payload"] if isinstance(result["payload"], list) else []
    print(f"\n找到 {len(models)} 个可用模型:\n")

    for model in models:
        model_id = model.get("id", "unknown")
        created = model.get("created", 0)
        created_date = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else "N/A"

        print(f"  📦 {model_id}")
        print(f"     创建时间: {created_date}")
        print(f"     价格: {format_pricing(model_id)}")
        print()

    return {"ok": True, "payload": models, "error": None}


def save_results(all_results: Dict[str, Any]) -> Path:
    """Append one record to the history file, written ATOMICALLY.

    The previous implementation truncated usage_history.json with open(...,"w")
    and then streamed ~1.1 MB of JSON into it. A crash, an OOM kill or a
    container restart mid-write left a truncated file that broke /api/history
    for good. Now we write a sibling temp file and os.replace() it, which is
    atomic on the same filesystem.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATA_DIR / "usage_history.json"

    history = {"records": []}
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, dict) or "records" not in history \
                    or not isinstance(history["records"], list):
                history = {"records": []}
        except Exception as e:
            print(f"⚠️  历史文件无法解析，将重建: {e}")
            history = {"records": []}

    history["records"].append(all_results)

    # Keep only last 100 records to prevent file from growing too large
    if len(history["records"]) > 100:
        history["records"] = history["records"][-100:]

    history["last_updated"] = datetime.now().isoformat()
    history["total_records"] = len(history["records"])

    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(DATA_DIR), prefix=".usage_history.", suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, filepath)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    print(f"\n📁 结果已保存: {filepath}")
    print(f"   历史记录数: {history['total_records']}")
    return filepath


def to_record(result: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize the {ok,payload,error} contract into the on-disk record shape.

    On disk the inner payload is stored under "data" (NOT "payload") so that
    the dashboard's existing `x?.data?...` accessors keep working against the
    100 legacy records already in usage_history.json.
    """
    return {"ok": result["ok"], "error": result["error"], "data": result["payload"]}


def main() -> int:
    """Main function. Returns a process exit code."""
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "   🤖 ZhipuAI Coding Plan 使用量查询工具".center(60) + "   ║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print(f"\n📅 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 API Key: {api_key_preview()}")
    print("🌐 平台: CN (open.bigmodel.cn)")

    # NOTE: there is deliberately NO chat/completions probe here any more.
    # It used to fire on every 15-minute cycle, burning real quota and adding
    # roughly a third of totalModelCallCount — the monitor was polluting the
    # very metric it was supposed to measure.
    results = {
        "quota_limits": query_quota_limits(),
        "model_usage": query_model_usage(),
        "tool_usage": query_tool_usage(),
        "models": query_available_models(),
    }

    ok_count = sum(1 for r in results.values() if r["ok"])
    total_queries = len(results)
    failures = [f"{k}: {v['error']}" for k, v in results.items() if not v["ok"]]

    all_results = {
        "query_time": datetime.now().isoformat(),
        "api_key_preview": api_key_preview(),
        "platform": "CN",
        "partial": ok_count < total_queries,
        "results": {k: to_record(v) for k, v in results.items()},
    }

    print("\n" + "=" * 70)
    print("📋 查询摘要 (SUMMARY)")
    print("=" * 70)
    print(f"\n✅ 成功查询: {ok_count}/{total_queries}")
    for line in failures:
        print(f"   ❌ {line}", file=sys.stderr)

    # A round where EVERYTHING failed must not be persisted: an all-zero record
    # would show up in the trend chart as a fake valley.
    if ok_count == 0:
        print("\n⛔ 全部查询失败，本轮不写入历史（避免趋势图出现假的 0 谷）", file=sys.stderr)
        print("\n" + "=" * 70)
        print("💥 查询失败!")
        print("=" * 70)
        return 1

    save_results(all_results)

    print("\n" + "=" * 70)
    print("✨ 查询完成!" if ok_count == total_queries else "⚠️  查询部分完成 (partial)")
    print("=" * 70)

    # 0 = all good, 2 = partial (record written, some endpoints failed),
    # 1 = total failure (nothing written).
    return 0 if ok_count == total_queries else 2


if __name__ == "__main__":
    sys.exit(main())
