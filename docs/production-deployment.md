# 小型生产部署指南

## 目标架构

```text
浏览器
  -> Nginx / React :8080
     -> FastAPI API :8000（容器内）
        -> MySQL（业务、用户、审计、Outbox）
        -> Redis（限流、并发锁、队列、进度事件）
        -> SSE（订单变化、知识入库进度）
     -> RQ Worker（解析、OCR、分块、Embedding、原子发布索引）
```

该组合适用于单机或一台小型云主机上的 10–50 名用户。生产环境建议至少 4 vCPU、8 GB
内存和 SSD；如果启用本地 BGE Embedding 或大量 OCR，建议 8 vCPU、16 GB 内存。

## 首次部署

1. 安装 Docker Desktop（Windows）或 Docker Engine + Compose（Linux 云主机）。
2. 从 `.env.example` 创建 `.env`，不要覆盖已有 `.env`。
3. 至少设置以下生产参数：

```env
APP_ENV=production
DATABASE_PROVIDER=mysql
MYSQL_ADMIN_PASSWORD=<独立强密码>
MYSQL_READONLY_PASSWORD=<独立强密码>
MYSQL_APP_PASSWORD=<独立强密码>
MYSQL_ORDER_PASSWORD=<独立强密码>
REDIS_REQUIRED=true
JOB_INLINE_FALLBACK=false
SESSION_COOKIE_SECURE=true
CSRF_ENABLED=true
PUBLIC_ORIGIN=https://agent.example.com
ALLOWED_ORIGINS=https://agent.example.com
FRONTEND_URL=https://agent.example.com
KNOWLEDGE_CORPUS=enterprise
```

真实模型还需要设置 `LLM_PROVIDER=openai_compatible` 以及模型地址、模型名和密钥。密钥只保存在
服务器的 `.env` 或云密钥管理服务中。

4. 启动全部服务：

```powershell
docker compose up -d --build
docker compose ps
```

`bootstrap` 只在业务表不存在时执行演示初始化；如果检测到现有 `users/orders`，它不会重建或
覆盖业务数据，只执行 Alembic 增量迁移和最小权限账户授权。

5. 验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health/live
Invoke-RestMethod http://127.0.0.1:8080/health/ready
docker compose logs --tail 100 api worker
```

## Windows 本地混合运行

若 API/前端在 Windows 主机运行，而 MySQL/Redis 使用 Docker：

```powershell
docker compose up -d mysql redis
.\.venv\Scripts\python.exe scripts\bootstrap_production.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开窗口启动 Worker：

```powershell
.\.venv\Scripts\python.exe -m app.jobs.worker
```

Redis 暴露在 `127.0.0.1:6379`，MySQL 默认暴露在 `127.0.0.1:3308`。开发环境允许 Redis
不可用时内联执行；生产环境应关闭该回退。

## 云端入口与安全

- 仅对公网开放 80/443；不要暴露 3306/3308、6379 或 API 容器端口。
- 在 Nginx 前增加云负载均衡器或反向代理并配置 TLS。
- 将 `PUBLIC_ORIGIN`、`ALLOWED_ORIGINS`、`FRONTEND_URL` 设置为实际 HTTPS 域名。
- 生产校验会拒绝不安全 Cookie、关闭 CSRF、缺少 Redis 或订单账户复用等配置。
- 普通 `user` 只能查订单；`order_operator` 可执行一般写操作；取消订单仅 `admin` 可确认。
- 所有订单写操作采用“准备 -> 显式确认”，并写入 `order_audit_logs` 与 `outbox_events`。

## 数据、备份与恢复

- MySQL：每日逻辑备份，并对恢复流程做季度演练。
- Redis：启用 AOF；它只保存可重建的队列/临时状态，不作为业务事实源。
- `nebula_knowledge`：保存原始知识文档和元数据。
- `nebula_app_data`：保存上传隔离区、索引版本、Trace 和 Checkpoint。
- 知识索引发布使用临时文件加原子替换；旧版本保留在 `data/vector_store/versions`。

升级前先备份数据库和两个应用卷，再执行 `docker compose up -d --build`。数据库结构由 Alembic
增量升级；不要在已有业务库上运行 `scripts/init_database.py`。

## 运维检查

- `/health/live`：进程存活。
- `/health/ready`：配置、数据库、Redis、知识索引是否可用。
- 订单 SSE：`/api/orders/events/stream`，可感知本系统写入和外部数据库更新。
- 知识任务 SSE：`/api/knowledge/jobs/{job_id}/events`。
- 日志中不要记录 Cookie、密码、模型密钥或完整敏感订单内容。

