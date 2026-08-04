# 架构与边界

## Web 交互增量架构

React/Vite 前端通过携带凭据的 Fetch 调用 FastAPI。认证使用服务端 Session：浏览器仅保存 HttpOnly Cookie，数据库只保存随机 Token 的 SHA-256 哈希。`app_users` 不复用演示业务 `users`；聊天会话和消息通过 `user_id`、`session_id` 外键隔离。

聊天消息路由只负责身份、所有权和持久化，Agent 执行仍调用现有 `run_agent(query, session_id)`。Agent 内部继续走真实 LangGraph → MCP Client → MCP Server → RAG/数据库/pytest/Chrome；回答完成后保存来源、request_id 和脱敏 Trace 摘要。

MySQL 使用三类账号：管理员仅负责初始化和 Alembic；`nebula_reader` 仅查询业务表；`nebula_app` 仅对四张 Web 表拥有 DML 权限。SQLite Mock/测试模式复用相同 SQLAlchemy 模型和 Alembic 迁移。

用户通过 FastAPI 或 `scripts/demo.py` 提交任务。LangGraph `StateGraph` 负责解析、规则式 Mock 规划、条件路由、工具结果分析和终止；每个工具调用均由正式 MCP Client 启动 stdio MCP Server 子进程并通过协议发现/调用工具。Server 内部调用 RAG、数据库、pytest/终端或 Playwright。

```text
FastAPI / CLI
  -> LangGraph StateGraph (AsyncSqliteSaver Checkpoint + thread_id)
     -> MCP Client --stdio--> MCP Server
        -> TF-IDF 词法检索
        -> SQLGlot AST -> SQLAlchemy -> MySQL / SQLite Mock
        -> subprocess(shell=False) -> pytest
        -> Playwright async API -> channel=chrome
  -> JSONL Trace（独立审计）
```

Checkpoint 位于 `data/checkpoints.sqlite`，保存图状态并支持同一 `thread_id` 的恢复语义。Trace 位于 `data/traces/{request_id}.jsonl`，保存节点、参数、摘要、时间与错误。Trace 不替代 Checkpoint。

运行模式：默认 `LLM_PROVIDER=mock`，只支持五个文档化任务的关键词规则规划；`EMBEDDING_PROVIDER=lexical` 使用中文字符 2–4 gram TF-IDF，是词法检索降级，不是语义向量。项目提供 OpenAI-compatible LLM/Embedding adapter，但因无 Key 未做外部调用验证。
