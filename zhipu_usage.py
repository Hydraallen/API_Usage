#!/usr/bin/env python3
"""
ZhipuAI Coding Plan Usage Query Script
Query account balance, usage statistics, and quota information

API Endpoints discovered from:
- https://github.com/guyinwonder168/opencode-glm-quota
- https://github.com/lgcyaxi/oh-my-claude

Author: E.D.I.T.H.
Created: 2026-03-04
Updated: 2026-03-04 - Added real usage monitoring APIs
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import quote
from pathlib import Path

# Load environment variables from .env file
def load_env():
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

# Configuration
API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
if not API_KEY:
    print("❌ 错误: 未找到 ZHIPUAI_API_KEY")
    print("   请创建 .env 文件并设置 ZHIPUAI_API_KEY=your_api_key")
    print("   或设置环境变量: export ZHIPUAI_API_KEY=your_api_key")
    exit(1)

BASE_URL = "https://open.bigmodel.cn"  # CN platform

# Token cost estimates (per million tokens, in CNY)
MODEL_PRICING = {
    "glm-5": {"input": 4, "output": 18},
    "glm-5-code": {"input": 6, "output": 28},
    "glm-4.7": {"input": 2, "output": 8},
    "glm-4.7-flashx": {"input": 0.5, "output": 3},
    "glm-4.7-flash": {"input": 0, "output": 0},  # Free
    "glm-4.5-air": {"input": 0.8, "output": 2},
    "glm-4-plus": {"input": 5, "output": 2.5},
    "glm-4-air": {"input": 0.5, "output": 0.25},
    "glm-4-flashx": {"input": 0.1, "output": 0.05},
    "glm-4-long": {"input": 1, "output": 0.5},
}

def make_request(endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict[str, Any]:
    """Make authenticated request to ZhipuAI API
    
    Note: Authorization header does NOT use "Bearer" prefix!
    """
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": API_KEY,  # No "Bearer" prefix!
        "Accept-Language": "en-US,en",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        else:
            response = requests.post(url, headers=headers, json=params, timeout=30)
        
        try:
            resp_data = response.json()
        except:
            resp_data = response.text
        
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200 and (isinstance(resp_data, dict) and resp_data.get("success", False)),
            "data": resp_data,
            "url": url
        }
    except Exception as e:
        return {
            "status_code": None,
            "success": False,
            "error": str(e),
            "url": url
        }

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
    """Query current quota limits
    
    Returns quota info for:
    - TOKENS_LIMIT (5 hour)
    - TOKENS_LIMIT (weekly)  
    - TIME_LIMIT (monthly MCP usage)
    """
    print("\n" + "="*70)
    print("📊 CODING PLAN 配额限制 (QUOTA LIMITS)")
    print("="*70)
    
    result = make_request("/api/monitor/usage/quota/limit")
    
    if result["success"] and isinstance(result["data"], dict):
        data = result["data"].get("data", {})
        limits = data.get("limits", [])
        level = data.get("level", "unknown")
        
        print(f"\n🏷️  账户等级: {level.upper()}")
        print()
        
        for limit in limits:
            limit_type = limit.get("type", "Unknown")
            unit = limit.get("unit", 0)
            number = limit.get("number", 0)
            percentage = limit.get("percentage", 0)
            next_reset = limit.get("nextResetTime", 0)
            
            if limit_type == "TOKENS_LIMIT":
                if unit == 3 and number == 5:
                    print(f"⏱️  5小时 Token 限额:")
                elif unit == 6 and number == 1:
                    print(f"📅 周度 Token 限额:")
                else:
                    print(f"📦 Token 限额 (Unit {unit}, {number}):")
                
                print(f"   {print_progress_bar(percentage)}")
                print(f"   重置时间: {format_timestamp(next_reset)} ({format_duration(next_reset - int(datetime.now().timestamp() * 1000))} 后)")
                print()
            
            elif limit_type == "TIME_LIMIT":
                print(f"🔧 MCP 工具使用限额 (月度):")
                print(f"   {print_progress_bar(percentage)}")
                print(f"   已用: {limit.get('usage', 0):,} / {limit.get('currentValue', 0) + limit.get('remaining', 0):,}")
                print(f"   剩余: {limit.get('remaining', 0):,}")
                print(f"   重置时间: {format_timestamp(next_reset)}")
                
                # Show usage details
                usage_details = limit.get("usageDetails", [])
                if usage_details:
                    print(f"\n   📈 工具使用详情:")
                    for detail in usage_details:
                        model = detail.get("modelCode", "unknown")
                        usage = detail.get("usage", 0)
                        print(f"      • {model}: {usage:,}")
                print()
        
        return result["data"]
    else:
        error = result.get("data", {}).get("msg", "Unknown error") if isinstance(result.get("data"), dict) else str(result.get("error", "Unknown"))
        print(f"❌ 查询失败: {error}")
        return result

def query_model_usage() -> Dict[str, Any]:
    """Query model usage statistics for 24-hour rolling window"""
    print("\n" + "="*70)
    print("🤖 模型使用统计 (MODEL USAGE - 24h)")
    print("="*70)
    
    start_time, end_time = get_time_window()
    params = {"startTime": start_time, "endTime": end_time}
    
    result = make_request("/api/monitor/usage/model-usage", params=params)
    
    if result["success"] and isinstance(result["data"], dict):
        data = result["data"].get("data", {})
        total_usage = data.get("totalUsage", {})
        
        total_calls = total_usage.get("totalModelCallCount", 0)
        total_tokens = total_usage.get("totalTokensUsage", 0)
        
        print(f"\n📊 总计 (24小时):")
        print(f"   📞 调用次数: {total_calls:,}")
        print(f"   🎫 Token 使用: {total_tokens:,}")
        print(f"\n📅 时间范围: {start_time} → {end_time}")
        
        # Show hourly breakdown (last 12 hours)
        x_time = data.get("x_time", [])
        tokens_usage = data.get("tokensUsage", [])
        call_counts = data.get("modelCallCount", [])
        
        if x_time:
            print(f"\n📈 最近12小时使用趋势:")
            recent_count = min(12, len(x_time))
            for i in range(-recent_count, 0):
                time_slot = x_time[i]
                tokens = tokens_usage[i] if tokens_usage[i] else 0
                calls = call_counts[i] if call_counts[i] else 0
                print(f"   {time_slot}: {tokens:>12,} tokens, {calls:>4} calls")
        
        return result["data"]
    else:
        error = result.get("data", {}).get("msg", "Unknown error") if isinstance(result.get("data"), dict) else str(result.get("error", "Unknown"))
        print(f"❌ 查询失败: {error}")
        return result

def query_tool_usage() -> Dict[str, Any]:
    """Query MCP tool usage statistics for 24-hour rolling window"""
    print("\n" + "="*70)
    print("🔧 工具使用统计 (TOOL/MCP USAGE - 24h)")
    print("="*70)
    
    start_time, end_time = get_time_window()
    params = {"startTime": start_time, "endTime": end_time}
    
    result = make_request("/api/monitor/usage/tool-usage", params=params)
    
    if result["success"] and isinstance(result["data"], dict):
        data = result["data"].get("data", {})
        total_usage = data.get("totalUsage", {})
        
        network_search = total_usage.get("totalNetworkSearchCount", 0)
        web_read = total_usage.get("totalWebReadMcpCount", 0)
        zread = total_usage.get("totalZreadMcpCount", 0)
        total_search = total_usage.get("totalSearchMcpCount", 0)
        
        print(f"\n📊 工具使用总计 (24小时):")
        print(f"   🔍 网络搜索: {network_search:,}")
        print(f"   📖 网页阅读: {web_read:,}")
        print(f"   📚 ZRead: {zread:,}")
        print(f"   📁 总计: {total_search:,}")
        
        # Show tool details
        tool_details = total_usage.get("toolDetails", [])
        if tool_details:
            print(f"\n📈 工具详情:")
            for detail in tool_details:
                model = detail.get("modelName", "unknown")
                count = detail.get("totalUsageCount", 0)
                print(f"      • {model}: {count:,}")
        
        return result["data"]
    else:
        error = result.get("data", {}).get("msg", "Unknown error") if isinstance(result.get("data"), dict) else str(result.get("error", "Unknown"))
        print(f"❌ 查询失败: {error}")
        return result

def query_available_models() -> List[Dict]:
    """Query available models"""
    print("\n" + "="*70)
    print("🤖 可用模型 (AVAILABLE MODELS)")
    print("="*70)
    
    result = make_request("/api/paas/v4/models")
    
    if result["success"] and isinstance(result["data"], dict):
        models = result["data"].get("data", [])
        print(f"\n找到 {len(models)} 个可用模型:\n")
        
        for model in models:
            model_id = model.get("id", "unknown")
            created = model.get("created", 0)
            created_date = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else "N/A"
            pricing = MODEL_PRICING.get(model_id, {"input": "?", "output": "?"})
            
            print(f"  📦 {model_id}")
            print(f"     创建时间: {created_date}")
            if pricing["input"] != "?":
                print(f"     价格: ¥{pricing['input']}/M 输入, ¥{pricing['output']}/M 输出")
            print()
        
        return models
    else:
        print(f"❌ 查询失败")
        return []

def test_chat_completion(model: str = "glm-4-flash") -> Dict[str, Any]:
    """Test a simple chat completion"""
    print("\n" + "="*70)
    print(f"💬 API 连通性测试 ({model})")
    print("="*70)
    
    url = f"{BASE_URL}/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",  # This endpoint uses Bearer prefix
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": "说'API测试成功'"}],
        "max_tokens": 50
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        resp_data = response.json()
        
        if response.status_code == 200:
            print("\n✅ API 测试成功!\n")
            
            choices = resp_data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                print(f"📝 响应: {content}")
            
            usage = resp_data.get("usage", {})
            if usage:
                print(f"\n📊 本次调用 Token:")
                print(f"   输入: {usage.get('prompt_tokens', 0):,}")
                print(f"   输出: {usage.get('completion_tokens', 0):,}")
                print(f"   总计: {usage.get('total_tokens', 0):,}")
            
            return {"success": True, "data": resp_data}
        else:
            print(f"❌ 测试失败: {resp_data.get('error', {}).get('message', 'Unknown')}")
            return {"success": False, "data": resp_data}
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return {"success": False, "error": str(e)}

def save_results(all_results: Dict[str, Any]) -> str:
    """Save results to a single JSON file with history"""
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage_history.json")
    
    # Load existing history if file exists
    history = {"records": []}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                history = json.load(f)
                if "records" not in history:
                    history = {"records": []}
        except:
            history = {"records": []}
    
    # Add new record
    history["records"].append(all_results)
    
    # Keep only last 100 records to prevent file from growing too large
    if len(history["records"]) > 100:
        history["records"] = history["records"][-100:]
    
    # Update metadata
    history["last_updated"] = datetime.now().isoformat()
    history["total_records"] = len(history["records"])
    
    # Save
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📁 结果已保存: {filepath}")
    print(f"   历史记录数: {history['total_records']}")
    return filepath

def main():
    """Main function"""
    print("╔" + "═"*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "   🤖 ZhipuAI Coding Plan 使用量查询工具".center(60) + "   ║")
    print("║" + " "*68 + "║")
    print("╚" + "═"*68 + "╝")
    print(f"\n📅 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 API Key: {API_KEY[:20]}...{API_KEY[-10:]}")
    print(f"🌐 平台: CN (open.bigmodel.cn)")
    
    all_results = {
        "query_time": datetime.now().isoformat(),
        "api_key_preview": f"{API_KEY[:20]}...{API_KEY[-10:]}",
        "platform": "CN",
        "results": {}
    }
    
    # Run all queries
    all_results["results"]["quota_limits"] = query_quota_limits()
    all_results["results"]["model_usage"] = query_model_usage()
    all_results["results"]["tool_usage"] = query_tool_usage()
    all_results["results"]["models"] = query_available_models()
    all_results["results"]["api_test"] = test_chat_completion()
    
    # Summary
    print("\n" + "="*70)
    print("📋 查询摘要 (SUMMARY)")
    print("="*70)
    
    success_count = sum(1 for r in all_results["results"].values() 
                       if isinstance(r, dict) and r.get("success"))
    total_queries = len(all_results["results"])
    print(f"\n✅ 成功查询: {success_count}/{total_queries}")
    
    # Save results
    save_results(all_results)
    
    print("\n" + "="*70)
    print("✨ 查询完成!")
    print("="*70)

if __name__ == "__main__":
    main()
