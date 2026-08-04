# 分阶段实施计划

| 阶段 | 目标与主要文件 | PowerShell 验证 | 完成标准 / 降级 |
|---|---|---|---|
| 初始化 | `pyproject.toml`、配置、FastAPI | `.venv\\Scripts\\python -m pytest`、健康请求 | 可安装启动；无 Key 用 Mock |
| 模拟业务 | 星云商城统一接口、错误码、订单场景 | 内容一致性测试 | `ORDER002` 横跨文档/数据/测试 |
| MySQL | Compose、schema、seed、只读账号 | `docker compose up -d mysql`、初始化查询 | 真实 MySQL；daemon 阻塞则 SQLite 仅作 Mock 降级 |
| 知识库/RAG | `knowledge_base/`、`app/rag/` | 构建脚本 + 五个中文问题 | 返回来源/片段/分数；TF-IDF 明示词法降级 |
| MCP | `app/mcp/server.py`、`client.py` | 工具发现与 stdio 集成测试 | 正式 SDK 跨进程调用 |
| LangGraph | `app/agent/` | 图结构、Checkpoint、E2E 测试 | StateGraph/条件边/thread_id/持久化状态 |
| pytest/终端 | 安全执行工具与可控失败测试 | `pytest -q`、`pytest -m demo_failure -v` | 默认全过；失败场景仅 marker |
| Chrome | Playwright `channel=chrome` | 浏览器集成测试 | 本机 Chrome 真启动、截图真实生成 |
| Trace | `app/tracing/` | Trace 查询测试 | 独立于 Checkpoint 的 JSONL 审计 |
| FastAPI | 健康、任务、Trace、重建接口 | uvicorn + HTTP 请求 | 接口响应符合 schema |
| 演示/验收 | `scripts/demo.py`、文档 | 五任务、全测试、服务清理 | 逐项标注实际/Mock/外部阻塞/未完成 |

