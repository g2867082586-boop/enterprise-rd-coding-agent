# 最终验收记录

验收时间：2026-07-18（Asia/Shanghai）。

| 项目 | 状态 | 真实结果摘要 |
|---|---|---|
| 环境与权限 | 已实际验证 | Windows、Python/Git、端口、Chrome、Key、包仓库完成 |
| 依赖安装 | 已实际验证 | 项目 `.venv` editable 安装成功，固定版本 |
| MySQL 启动 | 已实际验证 | MySQL 8.4 容器在宿主机 3308 端口 healthy，未影响 3306/3307 现有服务 |
| 数据库初始化/查询 | 已实际验证 | MySQL 2 users/6 orders；七天分组 ORDER002=3、ORDER003=1；业务账号仅 SELECT |
| 知识库构建 | 已实际验证 | 7 个有效源文件、10 chunks；五个中文问题有来源/片段/分数 |
| MCP Server/Client | 已实际验证 | 正式 SDK stdio，发现 8 工具并跨进程调用 |
| LangGraph | 已实际验证 | StateGraph、显式/条件边、AsyncSqliteSaver、thread_id、资源清理通过 |
| FastAPI | 已实际验证 | health、POST Agent、Trace 查询均真实 HTTP 验证 |
| 五个任务 | 使用 Mock 验证 | Mock LLM + 词法检索；MCP 工具调用数 1/3/2/1/5；均完成 |
| pytest 默认回归 | 已实际验证 | 新增功能后 34 passed, 1 deselected, 77 warnings, exit 0 |
| 受控失败 | 已实际验证 | 1 failed, 23 deselected, 1 warning, exit 1（预期分析场景） |
| Chrome | 已实际验证 | `channel=chrome`、HTTP 200、文本/元素、无控制台错误、真实截图 |
| 用户认证 | 已实际验证 | Argon2、注册/登录/注销、HttpOnly Cookie、Session 撤销、禁用账号和统一错误通过 |
| 聊天与权限 | 已实际验证 | 会话/消息持久化、真实 Agent 调用、来源、历史、跨用户隔离和 Trace 归属通过 |
| Alembic/MySQL Web 权限 | 已实际验证 | SQLite 升级/回滚；MySQL 迁移；nebula_app 可操作四张 Web 表且不能读取 orders |
| React 前端 | 已实际验证 | 当前锁定依赖安装成功；4 个 Vitest 测试和生产构建通过 |
| Chrome Web E2E | 已实际验证 | 注册→登录→会话→真实 Agent→来源→刷新历史→注销→路由保护全流程通过 |
| Trace | 已实际验证 | API 样例读取 6 个事件；Checkpoint 与 Trace 分离 |
| 外部真实 LLM/Embedding | 因外部条件未验证 | 未检测到 Key；adapter 已实现但未发请求 |
| 服务清理 | 已实际验证 | 项目 uvicorn 已停止且无残留；浏览器上下文均关闭 |

尚未完成：真实 LLM 和真实语义 Embedding 调用，原因是未配置外部 Key。前后端核心闭环仍明确使用 Mock LLM 与 TF-IDF 词法检索，没有将其描述为真实模型推理或语义向量检索。
