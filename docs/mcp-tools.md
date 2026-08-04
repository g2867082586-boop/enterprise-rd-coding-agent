# MCP 工具

Server：`.venv\Scripts\python -m app.mcp.server`（stdio）。发现/调用验证：`.venv\Scripts\python scripts\mcp_smoke.py`。

| 工具 | 作用 | 关键限制 |
|---|---|---|
| `search_knowledge_base` | 返回标题、来源、片段、相关度、元数据 | top_k 1–10；明确 TF-IDF 词法模式 |
| `list_tables` / `describe_table` | 查看允许表和字段 | 仅四张业务/审计表 |
| `execute_readonly_sql` | AST 校验后查询 | 单语句、表白名单、危险函数拒绝、LIMIT、脱敏 |
| `natural_language_query` | Mock NL-to-SQL | 仅预设“最近七天失败订单”问题 |
| `run_terminal_command` | 结构化质量检查命令 | 仅允许 pytest/ruff，限制危险选项和越界路径；固定 cwd、`shell=False`、DEVNULL stdin、超时/截断 |
| `create_code_workspace` / `discard_code_workspace` | 编码任务工作区生命周期 | 基于当前 HEAD 创建/清理 detached Git worktree，模型修改与主工作区隔离 |
| `list_repository` / `search_code` / `read_code_file` | 代码理解 | 限定仓库根目录、过滤依赖与构建目录、限制文件和返回大小 |
| `apply_code_patch` / `get_code_diff` | 补丁与审查 | 仅在隔离 worktree 中执行 `git apply --check` 和补丁应用，输出可审查 diff |
| `run_code_checks` | 补丁验证 | 仅允许执行 worktree 内 `tests/` 下的 pytest 目标，并限制超时与输出大小 |
| `run_coding_task` | Coding Agent 闭环 | 在隔离 worktree 中执行代码上下文检索、结构化补丁生成、`git apply`、pytest 验证及最多 3 轮失败反馈修复 |
| `run_pytest` | 真 pytest 与统计 | 默认回归或显式 `demo_failure` marker |
| `browser_check` | 本地页面验证 | async Playwright、`channel=chrome`、host 白名单、禁止下载 |

日志区分 Agent 选工具、`MCP_CLIENT_REQUEST/RESPONSE`、`MCP_SERVER_EXECUTE/RETURN`。stdout 留给 MCP 协议，Server 日志写 stderr。
