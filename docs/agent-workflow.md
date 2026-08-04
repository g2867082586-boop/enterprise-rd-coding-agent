# LangGraph 工作流

图由 `START -> parse_request -> make_plan -> retrieve_knowledge -> select_tool` 开始。`select_tool` 使用条件边：高风险动作进入 `human_approval` 预留节点，普通工具进入 `execute_tool`，无剩余工具进入最终答案。执行后经 `analyze_result -> decide_next`，条件边决定继续选择或汇总，最后 `generate_final_answer -> save_trace -> END`。

状态使用 `TypedDict`，包含 request/thread ID、意图、计划、当前步、工具参数/结果、检索文档、错误、状态、迭代数和审批动作。安全上限由 `MAX_AGENT_ITERATIONS`、`MAX_TOOL_CALLS` 和 LangGraph `recursion_limit` 共同限制。

每个请求使用唯一 `thread_id`。最终图使用 `AsyncSqliteSaver` 持久化，应用 shutdown、测试 teardown 和 CLI finally 均关闭连接，避免后台线程泄漏。

