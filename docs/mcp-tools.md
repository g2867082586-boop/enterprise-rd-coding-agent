# MCP 工具

Server：`.venv\Scripts\python -m app.mcp.server`（stdio）。发现/调用验证：`.venv\Scripts\python scripts\mcp_smoke.py`。

| 工具 | 作用 | 关键限制 |
|---|---|---|
| `search_knowledge_base` | 返回标题、来源、片段、相关度、元数据 | top_k 1–10；明确 TF-IDF 词法模式 |
| `list_tables` / `describe_table` | 查看允许表和字段 | 仅四张业务/审计表 |
| `execute_readonly_sql` | AST 校验后查询 | 单语句、表白名单、危险函数拒绝、LIMIT、脱敏 |
| `natural_language_query` | Mock NL-to-SQL | 仅预设“最近七天失败订单”问题 |
| `run_terminal_command` | 结构化质量检查命令 | 仅允许 pytest/ruff，限制危险选项和越界路径；固定 cwd、`shell=False`、DEVNULL stdin、超时/截断 |
| `run_pytest` | 真 pytest 与统计 | 默认回归或显式 `demo_failure` marker |
| `browser_check` | 本地页面验证 | async Playwright、`channel=chrome`、host 白名单、禁止下载 |

日志区分 Agent 选工具、`MCP_CLIENT_REQUEST/RESPONSE`、`MCP_SERVER_EXECUTE/RETURN`。stdout 留给 MCP 协议，Server 日志写 stderr。
