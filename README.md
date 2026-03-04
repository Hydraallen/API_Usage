# ZhipuAI Coding Plan 使用量查询工具

查询智谱AI Coding Plan账户使用情况的脚本工具。

## 🎉 重要发现

通过研究开源项目发现，智谱AI **确实提供了使用量监控API**，只是没有公开文档！

**参考项目**:
- [opencode-glm-quota](https://github.com/guyinwonder168/opencode-glm-quota) - OpenCode插件
- [oh-my-claude](https://github.com/lgcyaxi/oh-my-claude) - Claude Code多代理插件

## 📊 API 端点

| 端点 | 用途 | 参数 |
|------|------|------|
| `/api/monitor/usage/quota/limit` | 配额限制 | 无 |
| `/api/monitor/usage/model-usage` | 模型使用量 (24h) | `startTime`, `endTime` |
| `/api/monitor/usage/tool-usage` | 工具使用量 (24h) | `startTime`, `endTime` |
| `/api/paas/v4/models` | 可用模型列表 | 无 |

## 🔑 认证方式

**重要**: 监控API **不使用** "Bearer" 前缀！

```bash
# ❌ 错误
Authorization: Bearer your_api_key

# ✅ 正确
Authorization: your_api_key
```

## 📈 查询结果示例

```
📊 CODING PLAN 配额限制
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏷️  账户等级: MAX

⏱️  5小时 Token 限额:
   [###-------------------------------------] 9.0%
   重置时间: 2026-03-04 18:06:32 (1小时 9分钟 后)

📅 周度 Token 限额:
   [####------------------------------------] 11.0%
   重置时间: 2026-03-10 15:05:07 (5天 21小时 后)

🔧 MCP 工具使用限额 (月度):
   [####------------------------------------] 12.0%
   已用: 4,000 / 4,000
   剩余: 3,503

🤖 模型使用统计 (24h)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📞 调用次数: 1,092
🎫 Token 使用: 47,353,865
```

## 🚀 使用方法

### 配置 API Key

1. 复制示例文件：
```bash
cp .env.sample .env
```

2. 编辑 `.env` 文件，填入你的 API Key：
```
ZHIPUAI_API_KEY=your_actual_api_key_here
```

### 运行脚本

```bash
# 运行查询脚本
python3 zhipu_usage.py

# 或者直接使用环境变量
export ZHIPUAI_API_KEY="your_api_key_here"
python3 zhipu_usage.py
```

### 查看可视化面板

```bash
# 方式1: 直接用浏览器打开
open dashboard.html

# 方式2: 启动本地服务器（推荐，支持自动刷新）
cd ~/.openclaw/workspace/API_Usage
python3 -m http.server 8080
# 然后访问 http://localhost:8080/dashboard.html
```

**功能特性**:
- 📊 实时显示配额限制（5小时/周度/月度）
- 🤖 模型使用统计（24小时）
- 🔧 MCP工具使用量
- 📈 Token使用趋势图
- 🔄 60秒自动刷新

## 📁 文件说明

```
API_Usage/
├── .gitignore          # Git忽略配置
├── .env                # API密钥（不提交）
├── .env.sample         # API密钥示例
├── zhipu_usage.py      # 主查询脚本
├── dashboard.html      # 可视化面板
├── usage_history.json  # 历史记录（自动生成，最多保留100条）
└── README.md           # 本文件
```

## 📊 数据字段说明

### 配额限制 (quota/limit)

| 字段 | 说明 |
|------|------|
| `TOKENS_LIMIT` (unit=3, number=5) | 5小时滚动窗口token限额 |
| `TOKENS_LIMIT` (unit=6, number=1) | 周度token限额 |
| `TIME_LIMIT` | 月度MCP工具使用限额 |
| `level` | 账户等级 (max, pro, lite等) |
| `percentage` | 使用百分比 |
| `nextResetTime` | 下次重置时间 (Unix ms) |

### 模型使用量 (model-usage)

| 字段 | 说明 |
|------|------|
| `totalModelCallCount` | 总调用次数 |
| `totalTokensUsage` | 总token使用量 |
| `x_time` | 时间轴 |
| `tokensUsage` | 每小时token使用 |
| `modelCallCount` | 每小时调用次数 |

### 工具使用量 (tool-usage)

| 字段 | 说明 |
|------|------|
| `totalNetworkSearchCount` | 网络搜索次数 |
| `totalWebReadMcpCount` | 网页阅读次数 |
| `totalZreadMcpCount` | ZRead调用次数 |
| `toolDetails` | 工具详情列表 |

## 🔧 集成建议

如果你想在自己的项目中使用这些API：

```python
import requests
from datetime import datetime, timedelta

def get_quota_limit(api_key: str) -> dict:
    """获取配额限制"""
    response = requests.get(
        "https://open.bigmodel.cn/api/monitor/usage/quota/limit",
        headers={
            "Authorization": api_key,  # 无Bearer前缀
            "Accept-Language": "en-US,en"
        }
    )
    return response.json()

def get_model_usage(api_key: str) -> dict:
    """获取24小时模型使用量"""
    now = datetime.now()
    start = now - timedelta(hours=24)
    
    response = requests.get(
        "https://open.bigmodel.cn/api/monitor/usage/model-usage",
        params={
            "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": now.strftime("%Y-%m-%d %H:%M:%S")
        },
        headers={
            "Authorization": api_key,
            "Accept-Language": "en-US,en"
        }
    )
    return response.json()
```

## 🌐 Web 控制台

如果需要更详细的信息，也可以访问：

- 财务概览: https://bigmodel.cn/finance/overview
- 用户权益: https://bigmodel.cn/usercenter/equity-mgmt/user-rights
- API Key 管理: https://bigmodel.cn/usercenter/proj-mgmt/apikeys

---

*创建时间: 2026-03-04*  
*最后更新: 2026-03-04*
