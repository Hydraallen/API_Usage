# Changelog

v1.3.0 及更早版本的记录见 README.md 的「更新日志」一节。

## [1.4.0] - 2026-10-10

### Features
- 多用户配置：新增 `ZHIPUAI_API_KEYS=Name1:key1,Name2:key2`，每项按第一个 `:` 切分。用户名白名单 `^[A-Za-z0-9_-]{1,32}$`；不合法、缺分隔符、Key 为空、重名的项被忽略，原因写入启动日志和 `GET /api/users` 的 `config_errors`，原因中不含 Key。
- 旧变量兼容：只配置 `ZHIPUAI_API_KEY` 时视为单用户，用户名取 `ZHIPUAI_DEFAULT_USER`（默认 `default`）。同时配置两者时以 `ZHIPUAI_API_KEYS` 为准，旧变量被忽略。
- 历史文件按用户拆分：第一个用户写 `usage_history.json`，其余用户写 `usage_history.<用户名>.json`。
- 采集器新增 `--user NAME` 参数；不带参数时按配置顺序依次查询全部用户。
- 后端按用户拆分状态、实时余额缓存（60 秒）、手动刷新节流（429）和「正在采集」锁（409）；后台调度按配置顺序逐个用户串行采集。
- 新路由 `GET /api/users`、`GET /api/overview`；`/api/status`、`/api/quota/live`、`/api/history`、`POST /api/refresh` 支持 `?user=`，不带参数时使用第一个用户。`user` 格式不合法返回 400，用户不存在返回 404，未配置任何 Key 返回 503（`/api/status` 不带参数时仍返回 200，供健康检查使用）。
- 面板：2 个及以上用户时显示总览表（用户 / 5h 配额 / 周配额 / 24h Tokens / 等级 / 最近采集）和用户切换按钮；选中的用户写入 URL `?user=`，支持刷新与浏览器前进后退。配额卡、模型 24h、工具 24h、趋势图、强制更新、倒计时、实时余额均针对当前用户。只有 1 个用户时总览表和切换按钮隐藏。
- 单个用户的历史文件缺失或损坏、Key 失效时，只有该用户显示错误，总览表中该行标记异常，其他用户正常显示。
- HTTP 服务器改为 `ThreadingHTTPServer`。

### Design Rationale
- 第一个用户沿用 `usage_history.json`：现网升级时只需把原账户放在 `ZHIPUAI_API_KEYS` 第一项，已有历史无需迁移。代价是文件名与用户顺序绑定，调整顺序会改变对应关系（README 已说明）。
- 所有标识（文件名、URL、日志）只由白名单校验后的用户名派生，不由 Key 派生，避免 Key 片段进入公开的 API 响应或文件名。
- 服务端调用采集器时 Key 不出现在 argv，子进程从继承的环境变量中按 `--user` 选择自己的 Key，`ps` 中只能看到用户名。子进程环境同时显式传入 `DATA_DIR`，保证服务端与采集器读写同一目录。
- 脱敏覆盖所有已配置的 Key（含被忽略配置项中的 Key），应用于 `last_error`、实时余额错误和写入历史文件的错误信息。
- `/api/overview` 只读取本地历史（按文件 mtime 缓存摘要）和已有的实时余额缓存，不触发上游请求，因此页面每 60 秒轮询一次不会增加上游调用；当实时余额缓存比最新历史记录新时，配额百分比取实时值（`quota_source: "live"`）。
- 改为线程化 HTTP 服务器：单个用户的实时余额请求最长阻塞 15 秒，单线程服务器下会拖住其他用户的请求；共享状态均由每用户的锁保护。
- 前端每次切换用户递增视图代号，旧视图的响应到达后被丢弃，避免慢请求把上一个用户的数据画到当前用户上。

### Notes & Caveats
- 采集器不再在 import 时因缺少 Key 而 `sys.exit(1)`；无 Key 时 `main()` 返回 1。服务端改为启动时直接 import `zhipu_usage`。
- 多用户串行采集：N 个用户一轮最长约 N × 60 秒（每个用户的子进程超时 60 秒）。
- 手动刷新节流按用户计算，N 个用户时公开的 `POST /api/refresh` 每分钟最多触发 N 次采集。
- `/api/status` 新增字段 `user`、`users`；`/api/history`、`/api/quota/live` 响应新增 `user` 字段。原有字段不变。
- 移动端（≤768px）趋势图隐藏柱顶数值，横轴每 4 个标签显示 1 个，避免页面出现横向滚动；总览表隐藏「等级」「最近采集」两列，错误原因只显示图标（悬停 / 详情区可见全文）。
- `.gitignore` 新增 `usage_history.*.json`。
