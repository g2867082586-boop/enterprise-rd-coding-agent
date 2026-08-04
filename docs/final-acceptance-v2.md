# V2 最终验收记录

## 已实际验证

- 真实 LangGraph 条件图、SQLite Checkpoint/thread_id 恢复状态和独立 JSONL 业务 Trace。
- 正式 MCP SDK stdio Client/Server；数据库工具返回 ORDER002=3、ORDER003=1。
- `BAAI/bge-small-zh-v1.5` 本地中文 Embedding：512 维、10 chunks、同义问法正确召回。
- V2 确定性评测：路由/工具/Hit@3/Recall@3/MRR 均为 100%，禁止工具率 0%。
- 后端全量回归：46 passed、1 deselected；前端 4 passed 且生产构建成功。
- 本机正式 Google Chrome E2E 包含在全量回归中。
- 审批持久化、权限、幂等批准和服务端参数恢复。
- DeepSeek V4 Flash 真实 API：健康检查、普通生成、结构化路由、Direct/Database/Hybrid 完整闭环均通过，无 Mock 降级。
- 真实模型路由评测复验：10/10，工具选择 10/10，禁止工具误调用率 0%。
- 本地 MySQL 8.4 容器：healthy；迁移、种子数据、只读账号与 6 个 MySQL 专项测试通过。

## 使用 Mock 验证

- 无 Key 下的七类路由、有限计划、Evidence Check、答案整理和回归演示。
- TF-IDF 仅作为明确的词法降级，不称为语义检索。

## 因外部条件未验证

- LangSmith 上报和 OTel OTLP 导出：未配置 Key/接收端。
- GitHub MySQL 容器 CI：工作流已实现，未在具有 CI Secrets 的远程 Runner 执行。

## 尚未完成

- 真实 LangSmith/OTLP 出站验证、远端 CI 运行结果。这些均不伪造为已通过。
