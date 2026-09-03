# 🤖 ZhipuAI Coding Plan 使用量监控

[![Docker](https://img.shields.io/badge/Docker-Supported-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**实时监控智谱AI Coding Plan 的使用量**。**零第三方依赖** —— 只用 Python 标准库，
clone 下来就能构建，构建期不需要访问 pypi。支持本地直接运行和 Docker 部署。

## 📸 预览

```
╔════════════════════════════════════════════════════════════════════╗
║                 🤖 ZhipuAI Coding Plan 使用量监控                    ║
╠════════════════════════════════════════════════════════════════════╣
║  状态: ✅ API 正常          账户等级: MAX                            ║
║  上次更新: 03-04 17:44:32   下次更新: 14分58秒                       ║
╠════════════════════════════════════════════════════════════════════╣
║  📊 配额限制                                                        ║
║  ├─ ⏱️ 5小时滚动窗口: [###-------] 14%                              ║
║  ├─ 📅 周度限额:     [####------] 12%                               ║
║  └─ 🔧 MCP工具限额:  [####------] 12%                               ║
╠════════════════════════════════════════════════════════════════════╣
║  🤖 模型使用 (24h)                                                  ║
║  ├─ 调用次数: 1,056                                                ║
║  └─ Token使用: 45.7M                                               ║
╠════════════════════════════════════════════════════════════════════╣
║  🔧 工具使用 (24h)                                                  ║
║  ├─ 🔍 search-prime: 21                                            ║
║  └─ 📖 web-reader: 5                                               ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📊 **配额监控** | 5小时/周度/月度配额使用情况 |
| 🤖 **模型统计** | 24小时调用次数、Token使用量 |
| 🔧 **工具统计** | 网络搜索、网页阅读等MCP工具使用量 |
| 📈 **趋势图表** | 双轴：柱状=区间真实增量，折线=24h 滚动累计总量 |
| ⚡ **秒开余额** | 打开页面先用历史快照即时出画面，同时并发拉 `/api/quota/live` 原地替换成最新余额 |
| 🔄 **自动刷新** | Docker模式每15分钟自动采集（只服务趋势图，不再决定页面新鲜度） |
| ⏰ **倒计时** | 显示距离下次更新的时间 |
| 🚀 **强制更新** | 一键手动触发数据刷新 |
| 🐳 **Docker支持** | `docker compose up -d --build` 一键部署 |
| 📦 **零依赖** | 不装任何 pip 包（`urllib` + `json` + `http.server`），构建期完全离线 |

---

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

**适合：常驻服务器 / 家庭服务器，24 小时自动采集**

#### 1️⃣ 克隆项目

```bash
git clone https://github.com/Hydraallen/API_Usage.git
cd API_Usage
```

#### 2️⃣ 配置 API Key

> 💡 **获取 API Key**：登录 [智谱AI开放平台](https://bigmodel.cn/usercenter/proj-mgmt/apikeys) 创建。

有两种等价方式，任选其一：

**方式 A：环境变量（推荐给 CI / 密钥管理器）**

在 `docker-compose.override.yml` 里注入（该文件已被 `.gitignore` 忽略）：

```yaml
services:
  api-usage-monitor:
    environment:
      - ZHIPUAI_API_KEY=<your_api_key>
```

或者用 `env_file:` 指向一个宿主机上的密钥文件：

```yaml
services:
  api-usage-monitor:
    env_file:
      - ./secrets.env      # 内容：ZHIPUAI_API_KEY=<your_api_key>
```

**方式 B：放进数据卷的 `.env`（`load_env()` 的回退路径）**

> ⚠️ 镜像 **不会** COPY `.env`。容器读的是数据卷里的 `/app/data/.env`，
> 也就是宿主机上 `${DATA_DIR}` 指向那个目录下的 `.env`。
> 放到仓库根目录对 Docker 模式**不生效**。

```bash
# DATA_DIR 默认是仓库目录下的 ./data
mkdir -p ./data
cp .env.sample ./data/.env
$EDITOR ./data/.env          # 填入你的 API Key
chmod 600 ./data/.env
```

`.env` 内容：
```
ZHIPUAI_API_KEY=<your_api_key>
```

#### 3️⃣ 启动服务

```bash
# 构建并启动（后台运行）。构建期不需要访问 pypi。
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

#### 4️⃣ 访问面板

打开浏览器访问 **http://<宿主机地址>:8080**（端口由 `HOST_PORT` 决定，默认 `8080`）。

#### 5️⃣ 私有部署：用 override 文件，别改仓库文件

`docker-compose.yml` 是**公共的、部署中立的**。宿主机路径、资源限制、镜像 tag、
密钥这些属于你自己的东西，请全部写进同目录的 `docker-compose.override.yml`
（Compose 会自动合并，且该文件已被 `.gitignore` 忽略），这样 `git pull` 永远不会冲突：

```yaml
# docker-compose.override.yml —— 示例，不要提交
services:
  api-usage-monitor:
    volumes:
      - /srv/appdata/API_Usage:/app/data
    environment:
      - ZHIPUAI_API_KEY=<your_api_key>
    deploy:
      resources:
        limits:
          memory: 256M
```

也可以只用环境变量而不写 override：

```bash
DATA_DIR=/srv/appdata/API_Usage HOST_PORT=9000 TZ=Asia/Shanghai \
  docker compose up -d --build
```

---

### 方式二：本地运行

**适合：临时查询，无需后台服务**

#### 1️⃣ 安装依赖

不需要。本项目**零第三方依赖**，任意 Python 3.9+ 直接跑：

```bash
python3 --version   # >= 3.9 即可，无需 pip install
```

#### 2️⃣ 配置 API Key

```bash
cp .env.sample .env
$EDITOR .env        # 填入 API Key
```

> 本地（非 Docker）运行时 `.env` **就放在脚本同目录**，与 Docker 模式不同。
> 想显式指定目录可以设 `DATA_DIR=/some/path`，脚本会从那里读 `.env`
> 并把 `usage_history.json` 写到那里。

#### 3️⃣ 运行查询

```bash
# 单次查询
python3 zhipu_usage.py

# 或使用环境变量
export ZHIPUAI_API_KEY="<your_api_key>"
python3 zhipu_usage.py
```

退出码：`0` = 全部成功，`2` = 部分成功（已写历史），`1` = 全部失败（不写历史）。

#### 4️⃣ 查看结果

- **终端输出**: 直接显示使用量信息
- **JSON文件**: `usage_history.json` 保存历史记录
- **可视化面板**: 启动 `server.py` 后访问 `/dashboard.html`

---

## 📁 项目结构

```
API_Usage/
├── 📄 docker-compose.yml   # 公共 Compose 配置（部署中立，勿改）
├── 📄 docker-compose.override.yml  # 你的私有覆盖（可选，已 gitignore）
├── 📄 Dockerfile           # Docker 镜像定义
├── 📄 server.py            # HTTP 服务器（Docker用）
├── 📄 zhipu_usage.py       # 核心查询脚本
├── 📄 dashboard.html       # 可视化监控面板
├── 📄 .env.sample          # 环境变量示例
├── 📄 .env                 # 本地运行用；Docker 模式请放到数据卷 ${DATA_DIR}/.env
├── 📄 .gitignore           # Git 忽略规则
├── 📄 README.md            # 本文档
└── 📄 usage_history.json   # 历史记录（自动生成，写在 DATA_DIR 下，原子替换）
```

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `ZHIPUAI_API_KEY` | ✅ | - | 智谱AI API Key。可用环境变量 / `env_file` 注入，或写进 `${DATA_DIR}/.env` |
| `DATA_DIR` | ❌ | Docker 下 `/app/data`（宿主侧默认 `./data`），本地为脚本所在目录 | `.env` 与 `usage_history.json` 的存放目录，`server.py` 和 `zhipu_usage.py` 共用 |
| `HOST_PORT` | ❌ | `8080` | **宿主机**发布端口，只影响 compose 的 `ports` 左半边 |
| `PORT` | ❌ | `8080` | **容器内**监听端口。一般不要动，改 `HOST_PORT` 就够了 |
| `TZ` | ❌ | `UTC` | 容器时区，例如 `Asia/Shanghai`。影响日志与 24h 窗口的本地时间显示 |
| `REFRESH_INTERVAL` | ❌ | `15` | 后台采集间隔（分钟），只喂趋势图；页面余额走 `/api/quota/live` |
| `LIVE_QUOTA_TTL` | ❌ | `60` | `/api/quota/live` 的内存缓存 TTL（秒） |

> ⚠️ `PORT` 是容器内端口，`HOST_PORT` 是宿主端口。只改 `HOST_PORT` 即可换访问端口；
> 把 `PORT` 改掉而不同步改映射右半边，页面会直接连不上。

### 修改刷新间隔 / 端口 / 数据目录

不要改 `docker-compose.yml`，用变量或 override 文件：

```bash
# 一次性
REFRESH_INTERVAL=30 HOST_PORT=9000 DATA_DIR=/srv/appdata/API_Usage docker compose up -d

# 或写进仓库目录下的 .env（Compose 自动读取，已被 .gitignore 忽略）
cat > .env <<'EOF2'
HOST_PORT=9000
DATA_DIR=/srv/appdata/API_Usage
REFRESH_INTERVAL=30
TZ=Asia/Shanghai
EOF2
docker compose up -d
```

---

## 🐳 Docker 常用命令

```bash
# 构建镜像
docker build -t zhipu-usage-monitor .

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 查看状态
docker compose ps

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 进入容器
docker exec -it api_usage_monitor /bin/bash
```

---

## 🌐 API 接口

Docker 模式下提供以下 API：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 仪表盘（等价于 `/dashboard.html`） |
| `/dashboard.html` | GET | 可视化监控面板 |
| `/api/status` | GET | 服务状态：`last_update` / `last_success_time` / `last_error` / `consecutive_failures` / `healthy` |
| `/api/quota/live` | GET | **按需实时余额**，只打上游一个只读接口，60 秒内存缓存 |
| `/api/history` | GET | 历史数据（趋势图数据源）；文件损坏时返回 500 + `error` 字段 |
| `/api/refresh` | POST | 触发强制采集（**仅 POST**；正在跑时返回 409） |

> 🔒 其余路径一律 404 —— 静态文件走白名单，`/server.py`、`/zhipu_usage.py`
> 不再能被下载。

`/api/quota/live` 返回：

```jsonc
// 成功 200
{ "ok": true, "cached": false, "age_seconds": 0, "ttl_seconds": 60,
  "fetched_at": "2026-09-03T05:00:00+00:00",
  "data": { "level": "max", "limits": [ ... ] }, "error": null }
// 失败 502（前端会显示错误徽标，不会降级成 0）
{ "ok": false, "cached": false, "age_seconds": 0, "ttl_seconds": 60,
  "fetched_at": "...", "data": null, "error": "..." }
```

示例：
```bash
# 获取状态
curl http://localhost:8080/api/status

# 实时余额（60 秒缓存）
curl http://localhost:8080/api/quota/live

# 触发刷新（POST，GET 会 404）
curl -X POST http://localhost:8080/api/refresh
```

---

## 📊 数据说明

### 配额类型

| 类型 | 说明 | 重置周期 |
|------|------|----------|
| 5小时滚动窗口 | Token使用量限制 | 每5小时 |
| 周度限额 | 每周Token总量 | 每周一 |
| MCP工具限额 | 搜索/阅读工具次数 | 每月 |

### 数据来源

通过研究开源项目发现的**非公开API**：
- [opencode-glm-quota](https://github.com/guyinwonder168/opencode-glm-quota)
- [oh-my-claude](https://github.com/lgcyaxi/oh-my-claude)

---

## 🔒 安全说明

- `.env` 文件包含敏感信息，**已自动忽略**提交到Git
- `usage_history.json` 只写脱敏预览（前 6 位 + 后 4 位），且**已自动忽略**提交到Git
- `docker-compose.override.yml`（私有路径 / 密钥）**已自动忽略**提交到Git
- 请勿在公开场合分享你的 API Key
- 服务只服务白名单静态文件，源码不可通过 HTTP 下载
- 接口不再下发 `Access-Control-Allow-Origin: *`，仅同源可读

---

## 🛠️ 故障排除

### 问题：API 返回 401 错误

**原因**：API Key 无效或过期

**解决**：
1. 检查 `.env` 文件中的 `ZHIPUAI_API_KEY` 是否正确
2. 登录 [智谱AI](https://bigmodel.cn/usercenter/proj-mgmt/apikeys) 确认API Key状态

### 问题：Docker 容器无法启动

**原因**：端口被占用或配置错误

**解决**：
```bash
# 检查端口占用
lsof -i :8080

# 修改端口
# 换一个宿主端口即可：HOST_PORT=9000 docker compose up -d
```

### 问题：页面显示"加载失败"

**原因**：数据文件不存在或为空

**解决**：
```bash
# 手动运行一次查询
docker exec -it api_usage_monitor python3 /app/zhipu_usage.py
```

### 问题：余额区域显示"实时余额获取失败"

**原因**：上游 `/api/monitor/usage/quota/limit` 打不通，或 `.env` 里没有可用 Key

**解决**：
```bash
# 直接看服务端给出的错误原因
curl -s http://localhost:8080/api/quota/live

# 看采集器最近一次失败原因
curl -s http://localhost:8080/api/status
```

> 页面此时展示的是最近一次采集的历史值，并带有明确的错误徽标 ——
> **不会**把余额降级成 0 或空白。

### 问题：自动刷新不工作

**解决**：
```bash
# 检查日志
docker compose logs -f

# 重启容器
docker compose restart
```

---

## 📝 更新日志

### v1.2.0 (2026-09-03)

- 📦 **零第三方依赖**：`requests` 全部换成标准库 `urllib.request`，新增内部
  `_http_request()` 统一收口所有 HTTP 调用。`parse_envelope()` 与
  `{ok, payload, error}` 契约、落盘记录格式**保持完全不变**，只换传输层
- 🐳 Dockerfile 删除 `RUN pip install` 层 —— **构建期不再需要任何出网**，
  镜像层数减少；`HEALTHCHECK` 端口改为运行时读 `$PORT`，不再硬编码
- 🧭 `docker-compose.yml` 改成部署中立：`${DATA_DIR:-./data}` /
  `${HOST_PORT:-8080}` / `TZ=${TZ:-UTC}`；私有路径、资源限制、密钥请写进
  `docker-compose.override.yml`
- 🔐 `api_key_preview` 由「前 20 + 后 10」收敛为「前 6 + 后 4」，
  日志与历史文件里泄露的 Key 字符数大幅减少
- 🩺 错误信息更可诊断：非 2xx 会读出响应体里的真实原因；响应不是 JSON 时
  给出 `JSONDecodeError` 原因 + 原文前 200 字符；超时与网络错误分别标注

### v1.1.0 (2026-09-03)

- ⚡ 新增 `GET /api/quota/live`：按需实时余额，60 秒内存缓存，页面打开即见最新值
- 🧹 移除周期性 `chat/completions` 探活 —— 它每 15 分钟真实消耗配额，
  约占 `totalModelCallCount` 的 1/3，污染了被监控指标本身
- 🐛 修复响应信封判定：`/api/paas/v4/models` 是 OpenAI 风格 `{object,data}`、
  没有 `success` 字段，旧代码 100/100 恒判失败
- 📈 趋势图改双轴：柱状=区间增量，折线=24h 累计；负增量与缺失值按"无数据"处理
- 🔊 失败不再静默：脚本非零退出，`/api/status` 暴露 `last_error` /
  `last_success_time` / `consecutive_failures`；全失败的轮次不写历史
- 💾 历史文件改为临时文件 + `os.replace()` 原子替换；`/api/history` 读损坏文件返回 500
- 🔒 静态文件白名单（`/server.py` 不再可下载）、去掉 CORS 通配、`/api/refresh` 仅 POST
- 🚀 首次采集移到后台线程，不再阻塞端口绑定最长 60 秒
- 🏷️ `MODEL_PRICING` 补 `GLM-5.3` / `GLM-5.3-Flash`，单价未经证实故显示"价格未知"
- 🛠️ 修正 Docker 哨兵文件 `/app/.dockerenv` → `/.dockerenv`，并统一由 `DATA_DIR` 环境变量决定数据目录

### v1.0.0 (2026-03-04)

- ✨ 初始版本发布
- 📊 支持配额限制、模型使用量、工具使用量查询
- 🐳 支持 Docker 部署
- 🔄 支持自动刷新和强制刷新
- 📈 可视化监控面板

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

[MIT License](LICENSE)

---

## 🔗 相关链接

- [智谱AI开放平台](https://bigmodel.cn/)
- [API Key管理](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)
- [财务概览](https://bigmodel.cn/finance/overview)

---

<p align="center">
  Made with ❤️ by Hydraallen
</p>
