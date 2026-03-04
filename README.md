# ZhipuAI Coding Plan 使用量查询工具

查询智谱AI Coding Plan账户使用情况的脚本工具，支持本地运行和Docker部署。

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

---

## 🚀 部署方式

### 方式一：Docker 部署（推荐）

适合部署到 NAS 服务器，支持自动刷新。

#### 1. 配置 API Key

```bash
# 复制示例文件
cp .env.sample .env

# 编辑 .env 文件
echo "ZHIPUAI_API_KEY=your_actual_api_key_here" > .env
```

#### 2. 启动容器

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

#### 3. 访问面板

打开浏览器访问: `http://your-nas-ip:8080`

#### 4. 自定义配置

编辑 `docker-compose.yml` 修改端口或刷新间隔：

```yaml
environment:
  - PORT=8080              # 服务端口
  - REFRESH_INTERVAL=15    # 自动刷新间隔（分钟）
```

修改后重启：
```bash
docker-compose down && docker-compose up -d
```

---

### 方式二：本地运行

#### 1. 配置 API Key

```bash
cp .env.sample .env
# 编辑 .env 填入 API Key
```

#### 2. 运行脚本

```bash
# 单次查询
python3 zhipu_usage.py

# 或使用环境变量
export ZHIPUAI_API_KEY="your_api_key_here"
python3 zhipu_usage.py
```

#### 3. 查看可视化面板

```bash
# 方式1: 直接打开
open dashboard.html

# 方式2: 本地服务器
python3 -m http.server 8080
# 访问 http://localhost:8080/dashboard.html
```

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📊 配额监控 | 5小时/周度/月度配额进度 |
| 🤖 模型统计 | 24小时调用次数、Token使用量 |
| 🔧 工具统计 | MCP工具使用量 |
| 📈 趋势图 | Token使用历史趋势 |
| 🔄 自动刷新 | Docker模式每15分钟自动更新 |
| ⏰ 倒计时 | 显示下次更新时间 |
| 🔄 强制更新 | 手动触发立即刷新 |

---

## 📁 文件说明

```
API_Usage/
├── Dockerfile           # Docker镜像配置
├── docker-compose.yml   # Docker Compose配置
├── server.py            # HTTP服务器（Docker用）
├── zhipu_usage.py       # 主查询脚本
├── dashboard.html       # 可视化面板
├── .env                 # API密钥（不提交）
├── .env.sample          # API密钥示例
├── .gitignore           # Git忽略配置
└── README.md            # 本文件
```

---

## 🐳 Docker 常用命令

```bash
# 构建镜像
docker build -t zhipu-usage-monitor .

# 手动运行
docker run -d \
  --name zhipu-usage-monitor \
  -p 8080:8080 \
  -v $(pwd)/.env:/app/data/.env:ro \
  zhipu-usage-monitor

# 查看日志
docker logs -f zhipu-usage-monitor

# 进入容器
docker exec -it zhipu-usage-monitor /bin/bash

# 重启容器
docker restart zhipu-usage-monitor
```

---

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

---

## 🔧 API 接口（Docker模式）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 重定向到 dashboard.html |
| `/dashboard.html` | GET | 可视化面板 |
| `/api/status` | GET | 获取服务状态 |
| `/api/history` | GET | 获取历史数据 |
| `/api/refresh` | GET/POST | 触发强制刷新 |

---

## 🌐 Web 控制台

- 财务概览: https://bigmodel.cn/finance/overview
- 用户权益: https://bigmodel.cn/usercenter/equity-mgmt/user-rights
- API Key 管理: https://bigmodel.cn/usercenter/proj-mgmt/apikeys

---

*创建时间: 2026-03-04*  
*最后更新: 2026-03-04*
