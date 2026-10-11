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
| 👥 **多用户** | 一个面板监控多个智谱账户：顶部总览表对比各用户配额，点选后看该用户完整详情；`?user=` 可直接分享 |

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

**多用户**：把 `ZHIPUAI_API_KEY` 换成 `ZHIPUAI_API_KEYS`，格式见下文
[多用户配置](#多用户配置)：

```yaml
      - ZHIPUAI_API_KEYS=Alice:<key_of_alice>,Bob:<key_of_bob>
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
# 单次查询（多用户时依次查询全部用户）
python3 zhipu_usage.py

# 只查询一个用户
python3 zhipu_usage.py --user Alice

# 或使用环境变量
export ZHIPUAI_API_KEY="<your_api_key>"
python3 zhipu_usage.py
```

退出码：`0` = 全部成功，`2` = 部分成功（已写历史），`1` = 全部失败（不写历史）。
查询多个用户时：全部为 0 才返回 `0`，全部失败返回 `1`，其余返回 `2`。

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
├── 📄 usage_history.json   # 第一个用户的历史记录（自动生成，写在 DATA_DIR 下，原子替换）
└── 📄 usage_history.<用户名>.json  # 其余用户各自的历史记录
```

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `ZHIPUAI_API_KEYS` | ✅¹ | - | 多用户：`Name1:key1,Name2:key2`。设置后 `ZHIPUAI_API_KEY` 被忽略 |
| `ZHIPUAI_API_KEY` | ✅¹ | - | 旧格式单用户 Key。可用环境变量 / `env_file` 注入，或写进 `${DATA_DIR}/.env` |
| `ZHIPUAI_DEFAULT_USER` | ❌ | `default` | 只配置 `ZHIPUAI_API_KEY` 时，这个唯一用户的用户名 |
| `DATA_DIR` | ❌ | Docker 下 `/app/data`（宿主侧默认 `./data`），本地为脚本所在目录 | `.env` 与 `usage_history.json` 的存放目录，`server.py` 和 `zhipu_usage.py` 共用 |
| `HOST_PORT` | ❌ | `8080` | **宿主机**发布端口，只影响 compose 的 `ports` 左半边 |
| `PORT` | ❌ | `8080` | **容器内**监听端口。一般不要动，改 `HOST_PORT` 就够了 |
| `TZ` | ❌ | `UTC` | 容器时区，例如 `Asia/Shanghai`。影响日志、24h 查询窗口，以及旧历史记录（无时区的时间字符串）按哪个时区解释。**不影响面板显示**：面板固定按北京时间 (UTC+8) 显示。已有历史时不要改动 `TZ`，否则旧记录的时间会被按新时区解释 |
| `REFRESH_INTERVAL` | ❌ | `15` | 后台采集间隔（分钟），只喂趋势图；页面余额走 `/api/quota/live` |
| `LIVE_QUOTA_TTL` | ❌ | `60` | `/api/quota/live` 的内存缓存 TTL（秒） |

¹ 两者至少配置一个。

> ⚠️ `PORT` 是容器内端口，`HOST_PORT` 是宿主端口。只改 `HOST_PORT` 即可换访问端口；
> 把 `PORT` 改掉而不同步改映射右半边，页面会直接连不上。

### 多用户配置

```
ZHIPUAI_API_KEYS=Alice:<key_of_alice>,Bob:<key_of_bob>
```

- 每项按**第一个** `:` 切分为「用户名:Key」（Key 本身含 `.`、不含 `:`）；项之间用 `,` 分隔，两侧空白会被去掉
- 用户名只允许 `A-Z a-z 0-9 _ -`，1–32 位。不合法、缺 `:`、Key 为空、用户名重复的项会被**忽略**，
  原因打印在启动日志里，并通过 `GET /api/users` 的 `config_errors` 返回（原因里不含 Key）
- 文件名、URL、日志只使用用户名，**不从 Key 派生任何标识**
- 设置了 `ZHIPUAI_API_KEYS` 时，它是唯一依据，`ZHIPUAI_API_KEY` 被忽略
- 只设置 `ZHIPUAI_API_KEY`（旧格式）时视为单用户，用户名取 `ZHIPUAI_DEFAULT_USER`（默认 `default`）

**历史文件布局（升级零迁移）**

| 用户 | 历史文件 |
|------|----------|
| 第一个用户（`ZHIPUAI_API_KEYS` 的第一项，或旧格式的唯一用户） | `usage_history.json`（与旧版本同一个文件） |
| 其余用户 | `usage_history.<用户名>.json` |

从单用户升级到多用户时，把原来的账户放在 `ZHIPUAI_API_KEYS` 的第一项，它会继续写原来的
`usage_history.json`，已有历史全部保留，不需要任何手工迁移。

> ⚠️ **原账户必须始终保持在 `ZHIPUAI_API_KEYS` 的第一位。删除第一项或调换顺序，
> `usage_history.json` 会改由新的第一个用户读写，导致历史错配（两个账户的记录混在同一个文件里）。**
> 需要调整顺序时，先停服务，手工按新顺序重命名历史文件，再启动。

用户名去重不区分大小写（`Bob` 与 `bob` 视为重名），因为大小写不敏感的文件系统上它们对应同一个历史文件。

**采集方式**：后台按配置顺序**逐个用户串行**采集；每个用户的状态、实时余额缓存、刷新节流、
「正在采集」锁相互独立，一个用户的 Key 失效只影响该用户，页面上其他用户照常显示。

**面板**：配置了 2 个及以上用户时，页面顶部显示总览表（用户 / 5h 配额 / 周配额 / 24h Tokens /
等级 / 最近采集）和用户切换按钮；选中的用户写进 URL `?user=`，刷新页面或分享链接都会停在该用户。
「强制更新」、倒计时、实时余额都只针对当前用户。只有 1 个用户时总览表和切换按钮自动隐藏，页面与旧版一致。

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

Docker 模式下提供以下 API。标 `?user=` 的接口按用户区分：**不带参数时使用第一个用户**，
因此旧客户端无需修改。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 仪表盘（等价于 `/dashboard.html`） |
| `/dashboard.html` | GET | 可视化监控面板 |
| `/api/users` | GET | 用户名列表 `{users:[{name,is_default}], default, config_errors}` |
| `/api/overview` | GET | 每用户一行：`level` / `five_hour_pct` / `weekly_pct` / `tokens_24h` / `calls_24h` / `record_time` / `healthy` / `last_error` 等。只读本地历史与已有的实时余额缓存，**不触发上游请求** |
| `/api/status?user=` | GET | 该用户的采集状态：`last_update` / `last_success_time` / `last_error` / `consecutive_failures` / `healthy`。不带参数且未配置任何 Key 时仍返回 200（健康检查用） |
| `/api/quota/live?user=` | GET | **按需实时余额**，只打上游一个只读接口，每用户 60 秒内存缓存；缓存过期时并发请求只会触发一次上游调用 |
| `/api/history?user=` | GET | 该用户的历史数据（趋势图数据源）；文件损坏时返回 500 + `error` 字段 |
| `/api/refresh?user=` | POST | 触发该用户的强制采集（**仅 POST**；该用户正在跑时返回 409，过快返回 429） |

`user` 参数错误时：格式不合法返回 `400`，用户不存在返回 `404`（响应带 `users` 列表），
未配置任何 Key 返回 `503`。

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

# 多用户
curl http://localhost:8080/api/users
curl http://localhost:8080/api/overview
curl "http://localhost:8080/api/history?user=Bob"
curl -X POST "http://localhost:8080/api/refresh?user=Bob"
```

---

## 📊 数据说明

### 配额类型

| 类型 | 说明 | 重置周期 |
|------|------|----------|
| 5小时滚动窗口 | Token使用量限制 | 每5小时 |
| 周度限额 | 每周Token总量 | 每周一 |
| MCP工具限额 | 搜索/阅读工具次数 | 每月 |

上游 `quota/limit` 接口按账户返回两种配额类型，面板与 `/api/overview` 都支持：

| `type` | 观察到的账户 | 字段 |
|--------|--------------|------|
| `TOKENS_LIMIT` | 旧账户（按 Token 计） | `unit` / `number` / `percentage` / `nextResetTime` |
| `CREDIT_LIMIT` | 新账户（积分制） | 另有 `usage`（积分上限）、`currentValue`（已用积分）、`remaining`（剩余积分） |

`CREDIT_LIMIT` 是新版 Coding Plan 的**积分额度**，积分不等于 Token（不同 Token 类型折算系数不同，
工具调用也扣积分）。官方公布的上限为 Lite 2000 / 10000、Pro 12000 / 60000、Max 28000 / 140000
（5 小时 / 每周），Pro 账户实测返回的 `usage` 与之一致。面板把它显示为「5小时积分额度」「每周积分额度」
并标注「已用 x / 12,000 积分」，不当作 Token 显示；`TOKENS_LIMIT` 仍显示为「5小时滚动窗口」「周度限额」。

窗口判定：`unit=3, number=5` 为 5 小时窗口，`unit=6, number=1` 为周窗口（两种类型相同）；
编码未知时按距 `nextResetTime` 的剩余时间判定（≤ 5 小时为 5 小时窗口，≤ 7 天为周窗口）。
百分比直接使用上游的 `percentage`（整数）；总览表的 5h / 周两列对两种类型都只显示百分比。

### 时间显示

面板上所有时间（上次更新、下次更新倒计时、最近采集、趋势图横轴、配额重置时间）一律按
**北京时间 (UTC+8)** 显示，不随浏览器时区变化。采集器从 1.4.1 起写入带时区偏移的时间
（如 `2026-10-11T10:01:08+08:00`）；旧记录中不带时区的时间由服务端按容器 `TZ` 补上偏移后再返回。

### 数据来源

通过研究开源项目发现的**非公开API**：
- [opencode-glm-quota](https://github.com/guyinwonder168/opencode-glm-quota)
- [oh-my-claude](https://github.com/lgcyaxi/oh-my-claude)

---

## 🔒 安全说明

- `.env` 文件包含敏感信息，**已自动忽略**提交到Git
- `usage_history.json` **不再写入任何与 Key 相关的字段**（`api_key_preview` 已彻底移除），且**已自动忽略**提交到Git
- `docker-compose.override.yml`（私有路径 / 密钥）**已自动忽略**提交到Git
- 请勿在公开场合分享你的 API Key
- 服务只服务白名单静态文件，源码不可通过 HTTP 下载
- 接口不再下发 `Access-Control-Allow-Origin: *`，仅同源可读
- 启动横幅只打印「已配置 / 未配置」与 Key 长度，**不输出 Key 的任何字符片段**
- `/api/status` 的 `last_error`、`/api/quota/live` 的 `error`、写进历史文件的错误信息都会做兜底脱敏，
  把**所有已配置用户**的 Key 原文替换为 `[REDACTED]`
- 服务端调用采集器时 Key 经环境变量传递，命令行只有 `--user <用户名>`，`ps` 里看不到 Key

### 关于公网暴露

**本项目的所有 HTTP 端点（页面与 `/api/*`）都是按「可公开访问」设计的**：

- 响应体里不含任何凭证、凭证片段、内网地址或宿主机路径
- `POST /api/refresh` 自带节流：每个用户默认 60 秒最多触发一次，超出返回 `429`
  （带 `Retry-After`），与「正在跑」的 `409` 语义区分；节流窗口可用
  `REFRESH_MIN_INTERVAL` 环境变量调整
- 静态文件走白名单，`/server.py` 之类一律 404

因此本项目**自身不内置任何认证机制**。如果你希望限制访问（例如只允许内网、
或加一层口令），请在反向代理层自行处理（Caddy `basic_auth`、Nginx
`auth_basic`、IP 白名单等）——应用层不会替你做这件事。

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

> 从 v1.4.0 起，版本级变更记录在 [CHANGELOG.md](CHANGELOG.md)。

### v1.4.0 (2026-10-10)

- 👥 多用户：`ZHIPUAI_API_KEYS=Name:key,...`，总览表 + 用户切换，详见 [CHANGELOG.md](CHANGELOG.md)

### v1.3.0 (2026-09-03)

- 🔐 **彻底移除 `api_key_preview`**：`api_key_preview()` 函数删除，落盘记录里
  不再有这个键，启动横幅改为只打印「已配置 / 未配置 + 长度」。
  历史文件与 `/api/history` 现在完全不含 Key 的任何字符
- 🚦 `POST /api/refresh` 新增节流：默认 60 秒一次，超出返回 `429` +
  `Retry-After`，前端收到 429/409 给出友好提示而不是报错
- 🛡️ `/api/status` 的 `last_error` 增加兜底脱敏（`_redact()`）
- 📖 README 新增「关于公网暴露」一节，明确端点可公开、认证由反代负责

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
