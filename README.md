# 🤖 ZhipuAI Coding Plan 使用量监控

[![Docker](https://img.shields.io/badge/Docker-Supported-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**实时监控智谱AI Coding Plan的使用量**，支持本地运行和Docker部署，完美适配NAS服务器。

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
| 📈 **趋势图表** | Token使用历史趋势可视化 |
| 🔄 **自动刷新** | Docker模式每15分钟自动更新数据 |
| ⏰ **倒计时** | 显示距离下次更新的时间 |
| 🚀 **强制更新** | 一键手动触发数据刷新 |
| 🐳 **Docker支持** | 一键部署到NAS或服务器 |

---

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

**适合：部署到NAS服务器，24小时自动监控**

#### 1️⃣ 克隆项目

```bash
git clone https://github.com/Hydraallen/API_Usage.git
cd API_Usage
```

#### 2️⃣ 配置 API Key

```bash
# 创建配置文件
cp .env.sample .env

# 编辑文件，填入你的智谱AI API Key
nano .env
```

`.env` 文件内容：
```
ZHIPUAI_API_KEY=your_api_key_here
```

> 💡 **获取API Key**: 登录 [智谱AI开放平台](https://bigmodel.cn/usercenter/proj-mgmt/apikeys) 创建API Key

#### 3️⃣ 启动服务

```bash
# 构建并启动（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 4️⃣ 访问面板

打开浏览器访问：**http://your-nas-ip:23098**

---

### 方式二：本地运行

**适合：临时查询，无需后台服务**

#### 1️⃣ 安装依赖

```bash
pip install requests
```

#### 2️⃣ 配置 API Key

```bash
cp .env.sample .env
# 编辑 .env 文件填入 API Key
```

#### 3️⃣ 运行查询

```bash
# 单次查询
python3 zhipu_usage.py

# 或使用环境变量
export ZHIPUAI_API_KEY="your_api_key_here"
python3 zhipu_usage.py
```

#### 4️⃣ 查看结果

- **终端输出**: 直接显示使用量信息
- **JSON文件**: `usage_history.json` 保存历史记录
- **可视化面板**: 用浏览器打开 `dashboard.html`

---

## 📁 项目结构

```
API_Usage/
├── 📄 docker-compose.yml   # Docker Compose 配置
├── 📄 Dockerfile           # Docker 镜像定义
├── 📄 server.py            # HTTP 服务器（Docker用）
├── 📄 zhipu_usage.py       # 核心查询脚本
├── 📄 dashboard.html       # 可视化监控面板
├── 📄 .env.sample          # 环境变量示例
├── 📄 .env                 # 环境变量（不提交）
├── 📄 .gitignore           # Git 忽略规则
├── 📄 README.md            # 本文档
└── 📄 usage_history.json   # 历史记录（自动生成）
```

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `ZHIPUAI_API_KEY` | ✅ | - | 智谱AI API Key |
| `PORT` | ❌ | 23098 | 服务端口（Docker用） |
| `REFRESH_INTERVAL` | ❌ | 15 | 自动刷新间隔（分钟） |

### 修改刷新间隔

编辑 `docker-compose.yml`：

```yaml
environment:
  - PORT=23098
  - REFRESH_INTERVAL=30  # 改为30分钟
```

修改后重启：
```bash
docker-compose down && docker-compose up -d
```

### 修改端口

编辑 `docker-compose.yml`：

```yaml
ports:
  - "9000:23098"  # 改为9000端口
```

---

## 🐳 Docker 常用命令

```bash
# 构建镜像
docker build -t zhipu-usage-monitor .

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 进入容器
docker exec -it zhipu-usage-monitor /bin/bash
```

---

## 🌐 API 接口

Docker 模式下提供以下 API：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 重定向到仪表盘 |
| `/dashboard.html` | GET | 可视化监控面板 |
| `/api/status` | GET | 获取服务状态 |
| `/api/history` | GET | 获取历史数据 |
| `/api/refresh` | POST | 触发强制刷新 |

示例：
```bash
# 获取状态
curl http://localhost:23098/api/status

# 触发刷新
curl -X POST http://localhost:23098/api/refresh
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
- `usage_history.json` 包含API Key预览，**已自动忽略**提交到Git
- 请勿在公开场合分享你的 API Key

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
lsof -i :23098

# 修改端口
# 编辑 docker-compose.yml 中的 ports 配置
```

### 问题：页面显示"加载失败"

**原因**：数据文件不存在或为空

**解决**：
```bash
# 手动运行一次查询
docker exec -it zhipu-usage-monitor python3 /app/zhipu_usage.py
```

### 问题：自动刷新不工作

**解决**：
```bash
# 检查日志
docker-compose logs -f

# 重启容器
docker-compose restart
```

---

## 📝 更新日志

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
