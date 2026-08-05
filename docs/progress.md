# 项目进度与真实验证记录

## V2 结构化路由、语义 RAG 与工作台（2026-07-19）

### 已完成

- Mock/OpenAI-compatible LLM Provider，严格 `RouteDecision`/`ExecutionPlan` Schema，七类条件路由，有限步骤/工具/重规划预算。
- 真实 LangGraph `StateGraph`、条件边、`AsyncSqliteSaver` 和 `thread_id`；答案与原始工具详情分离。
- 修复 Windows MCP 子进程未继承运行时数据库环境的问题；数据问题不再误调知识库。
- FastEmbed 本地中文语义、OpenAI-compatible Embedding、TF-IDF 降级、RRF 排序、权限/语料/阈值过滤和索引兼容检查。
- Markdown/TXT/PDF 可提取文本/DOCX/JSON/CSV 导入，模拟/企业语料隔离，去重元数据与轻量目录。
- 持久化审批、批准/拒绝/恢复 API、幂等与服务端参数保护；LangSmith/OTel 可选初始化。
- 路由/RAG/答案/Hybrid 评测数据与报告、MySQL 8.4 CI，前端知识库/审批/运行概览/折叠执行详情。

### 实际验证

- 改造前基线：`33 passed, 1 failed, 1 deselected, 77 warnings`；失败根因为 MCP 子进程误读 MySQL 环境，现已修复。
- 真实本地 Embedding：`BAAI/bge-small-zh-v1.5`、512 维、10 chunks、0 failed。同义问法语义分 0.5382，词法分 0.0238，正确召回用户接口文档。
- 真实 MCP stdio 数据库调用返回 `ORDER002=3`、`ORDER003=1`。
- 前端 `npm test -- --run`：`4 passed`；`npm run build`：退出码 0。
- 审批恢复与聊天聚焦回归：`2 passed`。评测文件位于 `artifacts/evaluation`。

### 当前问题

- DeepSeek V4 Flash 真实 LLM 已配置并实际验证；健康检查、普通生成、Pydantic 结构化路由、Direct/Database/Hybrid 完整闭环均未发生 Mock 降级。
- LangSmith 未配 Key，OTel 未配导出端点。GitHub CI 需配置三个 CI Secret 后由远端 Runner 验证；不伪造通过状态。

### 降级或替代方案

- 无 Key 时显式 Mock；本地 Embedding 初始化失败时，仅在 `ALLOW_MOCK_FALLBACK=true` 时降级为 TF-IDF，并在 API/Trace 中标记原因。

### 下一步

- 如需出站观测，分别配置 LangSmith 独立 Key 或 OTLP Collector/APM 端点；LLM Key 不可替代它们。

### 最终回归更新

- `python scripts/evaluate_v2.py`：路由准确率 100%，工具选择 100%，禁止工具误调用率 0%，Hit Rate@3/Recall@3/MRR 均为 100%，0 错误样本。
- SQLite `alembic upgrade head`：`20260718_01 -> 20260719_02` 成功。
- `pytest -q`：`46 passed, 1 deselected, 77 warnings in 157.88s`，退出码 0，包含本机 `channel="chrome"` E2E。
- Docker Desktop Linux Engine 已恢复，MySQL 8.4 容器为 healthy；迁移、种子数据、只读账号和 6 个 MySQL 专项测试已实际通过。远程 GitHub Actions 仍需推送仓库后验证。

### 真实模型与 MySQL 复验（2026-07-19）

- DeepSeek 健康检查：`ok=true`，模型 `deepseek-v4-flash`。
- 首轮真实路由评测：8/10；修复错误码/Hybrid 边界后复验 10/10，工具选择 10/10，禁止工具误调用率 0%。首轮和复验报告均保留。
- Direct：真实 LLM 直接回答，0 工具；Database：真实 LLM 路由后经 MCP/MySQL 返回 4 笔失败订单；Hybrid：动态计划调用 `natural_language_query` + `search_knowledge_base`，两步均成功，证据充分，无错误。
- MySQL 专项：`6 passed`，覆盖连接、种子结果、LIMIT、多语句/写操作/非白名单表/危险函数拒绝以及数据库服务端只读权限。

状态标签：`已实际验证`、`使用 Mock 验证`、`因外部条件未验证`、`尚未完成`。

## 需求阅读与环境检查

### 已完成

- 以 UTF-8 分段完整读取两份规范至文件末尾。
- 确认真实 MCP、真实 LangGraph、Checkpoint/Trace 分离、安全边界及最终验收要求。
- 检查 OS、Python、Git、Docker、3306、Key、Chrome、Playwright、包仓库和根目录。

### 实际验证

- 执行命令：`python --version`、`git --version`、`docker version`、`docker compose version`、PowerShell 端口与文件检查、`pip index versions pip`。
- 返回结果：Windows 10.0.26200；Python 3.12.10；Git 2.52.0；Docker CLI 29.5.3 / Compose 5.1.4；Docker daemon 未运行；3306 已占用；Chrome 已安装；Playwright 包未安装；包仓库可访问；无 LLM/Embedding Key。
- 是否通过：环境信息已实际验证；Chrome 启动待安装 Playwright 后验证。

### 当前问题

- Docker Desktop Linux daemon 未运行，且 3306 已被用户现有进程占用。

### 降级或替代方案

- 项目初始计划映射到 3307；后续发现 3307 也被原生 MySQL 占用，当前已调整为 3308，不触碰现有服务。
- Mock 演示先使用 SQLite 兼容后端；不得描述为 MySQL 已验证。
- 默认 Mock LLM；默认中文字符 n-gram TF-IDF 词法检索，不描述为语义向量检索。

### 下一步

- 创建虚拟环境、安装锁定依赖并验证 FastAPI 健康接口。

## 阶段一：项目初始化

### 已完成

- 已创建 Python 配置、环境变量样例、Git/Docker 配置和基础文档。

### 实际验证

- 执行命令：从本地用户目录设置 `$ProjectRoot` 并执行 `Set-Location -LiteralPath $ProjectRoot`，随后运行 `.\.venv\Scripts\python.exe -m pytest tests\unit -q`。
- 返回结果：cwd 正确解析到项目根目录；`scripts\demo.py` 存在；Python 正确解析到项目 `.venv`；13 passed in 2.30s，退出码 0。
- 是否通过：已实际验证。

### 当前问题

- 无。

### 降级或替代方案

- 无 Key 默认 Mock；MySQL 不可用时仅 Mock 演示使用 SQLite。

### 下一步

- 安装依赖并创建应用骨架。

## 阶段一：项目初始化（完成更新）

### 已完成

- 创建 `.venv`、锁定 Python 3.12 核心依赖、FastAPI、`.env.example`、Git/Docker 配置和 PowerShell README。

### 实际验证

- 执行命令：`python -m venv .venv`；`.venv\Scripts\python -m pip install -e .`；`python -m compileall -q app scripts tests`。
- 返回结果：editable wheel 构建并安装成功；全项目语法编译退出 0。
- 是否通过：已实际验证。

### 当前问题

- Docker daemon 未运行。

### 降级或替代方案

- SQLite 仅承担 Mock 演示，不替代 MySQL 验收结论。

### 下一步

- 统一业务、数据库和知识库。

## 阶段二至四：模拟业务、数据库、知识库/RAG

### 已完成

- 创建星云商城 7 个有效知识源、10 个 chunk；`ORDER002` 对应库存预占超时并贯穿文档、订单和测试。
- 创建 MySQL/SQLite schema、UTC 相对时间数据、独立只读 MySQL 账号初始化逻辑。
- 实现 Markdown/TXT/JSON、清洗、分块、TF-IDF 检索、来源/片段/相关度。

### 实际验证

- 执行命令：`scripts\init_database.py`、`scripts\seed_database.py`、`scripts\build_knowledge_base.py`、五问检索、`docker compose config --quiet`。
- 返回结果：2 users/6 orders；最近七天 ORDER002=3、ORDER003=1，十天前订单排除；10 chunks；五问均返回预期资料；Compose 配置退出 0。
- 是否通过：SQLite/检索已实际或 Mock 验证；真实 MySQL 因 daemon 未运行而未验证。

### 当前问题

- 3306 是 PID 10332 的现有 `mysqld`，后续 3307 也检测到 PID 10340 的原生 `mysqld`；未停止、重置或尝试未知凭据。项目当前使用 3308。

### 降级或替代方案

- TF-IDF 明确标记词法检索降级；保留外部 Embedding Provider。

### 下一步

- MCP 与 LangGraph。

## 阶段五至十：安全工具、MCP、LangGraph、Trace、FastAPI、Chrome

### 已完成

- SQL AST、终端/URL 守卫；正式 MCP stdio Server/Client 和 8 tools。
- 真实 StateGraph、10 个显式节点、条件边、AsyncSqliteSaver/thread_id、审批预留节点。
- 独立 JSONL Trace；FastAPI；async MCP Chrome 与 sync 测试 Chrome。

### 实际验证

- 执行命令：`scripts\mcp_smoke.py`、`pytest tests\integration -q`、`pytest tests\browser -q`、uvicorn + `Invoke-RestMethod`。
- 返回结果：发现 8 MCP tools；集成 4 passed；浏览器 1 passed；Chrome HTTP 200/文本/元素/截图/无控制台错误；API Agent 1 tool、Trace 6 events。
- 是否通过：已实际验证。

### 当前问题

- 初次同步 Checkpointer 与 async 图不兼容，已改 AsyncSqliteSaver；初次 favicon 404 与 MCP sync Playwright 错误已修复；pytest stdin 继承导致 60 秒超时已用 DEVNULL 修复。

### 降级或替代方案

- 无。

### 下一步

- 全量测试、五演示和最终文档。

## 阶段十一至十四：测试、五个演示与最终验收

### 已完成

- 单元、集成、浏览器、默认回归、受控失败和五任务全部执行。
- FastAPI 服务与悬挂测试进程均按项目范围清理；未改动现有 MySQL/Chrome。

### 实际验证

- 执行命令：`pytest tests\unit -q`、`pytest -q`、`pytest -m demo_failure -v -o "addopts="`、`scripts\demo.py`。
- 返回结果：单元 13 passed；最终全量 23 passed/1 deselected/62 warnings/exit 0；受控场景 1 failed/23 deselected/1 warning/exit 1（预期）；五演示状态均 completed，MCP tool 数 1/3/2/1/5。
- 是否通过：Mock 演示与无需外部条件的核心闭环已通过。

### 当前问题

- 真实 MySQL、真实 LLM、真实语义 Embedding 尚未执行。

### 降级或替代方案

- Mock LLM + TF-IDF + SQLite 明确标记；外部 adapter/MySQL 路径已实现但不声称验证成功。

### 下一步

- Docker daemon 可用并在本地 `.env` 配置密码后执行真实 MySQL 单独验收；提供 Key 时再验证对应外部 adapter。

## README 工作目录修复

### 已完成

- 根据用户截图确认命令从本地用户目录执行，误用了该目录下另一套 `.venv`。
- README 和演示指南现要求每个新 PowerShell 先 `Set-Location` 到项目根目录，并加入文件存在性校验；Python 路径统一写为 `.\.venv\Scripts\python.exe`。

### 实际验证

- 执行命令：对现有 `.env` 计算 SHA-256 前后摘要，执行新的条件创建逻辑，再编译 `scripts/init_database.py`。
- 返回结果：`.env_exists_preserved=true`、`env_hash_unchanged=True`；两处 Copy-Item 均位于不存在性判断内部；脚本编译退出码 0。未读取或输出 `.env` 内容。
- 是否通过：已实际验证。

### 当前问题

- 无项目代码故障；原问题是相对路径的工作目录不正确。

### 降级或替代方案

- 无。

### 下一步

- 用户在每个 PowerShell 窗口按修订后的 README 先切换目录，再执行演示或测试。

## `.env` 被模板覆盖修复

### 已完成

- 定位 README 中两处无条件 `Copy-Item .env.example .env`，确认第二次执行会清空用户已填写的密码。
- 所有复制命令改为仅在 `.env` 不存在时创建；MySQL 指南改为先编辑、保存和关闭 `.env`，再启动与初始化。
- 数据库初始化错误信息增加“不应再次覆盖 `.env`”提示。

### 实际验证

- 执行命令：待执行。
- 返回结果：待记录。
- 是否通过：尚未完成。

### 当前问题

- 已被覆盖的密码无法从空模板恢复，需要用户重新生成并填写；不得将密码发送到对话中。

### 降级或替代方案

- SQLite Mock 模式无需数据库密码，可继续运行非 MySQL 演示。

### 下一步

- 用户重新生成并填写两个密码，保存 `.env` 后直接从 `docker compose up -d mysql` 继续，不再复制模板。

## Docker Engine 与 3307 端口冲突诊断

### 已完成

- 确认 Docker Desktop `desktop-linux` Engine API 无响应/返回 500；这不是 Compose YAML 或数据库密码错误。
- 确认 3306（PID 10332）与 3307（PID 10340）均由本机原生 `mysqld` 监听；初始化脚本此前误连 3307，因项目随机密码与现有实例不匹配而返回 MySQL 1045。
- 将项目 Docker MySQL 默认端口从 3307 调整为当前空闲的 3308；未停止或修改任何现有 MySQL/Docker Desktop 服务。

### 实际验证

- 执行命令：Docker context/version/info 只读检查；`Get-NetTCPConnection` 检查 3306–3312；非敏感 Settings 检查。
- 返回结果：context 为 `desktop-linux`；Engine 命令无响应；3306/3307 均为 mysqld；3308–3312 空闲；项目成功读取 provider=mysql 和两个非空密码。3308 Compose 配置校验退出 0；脚本编译通过；单元测试 13 passed。
- 是否通过：根因已实际确认；Docker MySQL 启动仍因 Engine 外部状态未验证。

### 当前问题

- 用户需要在 Docker Desktop UI 中重启 Engine，并手工将本地 `.env` 的 `MYSQL_PORT` 改为 3308。

### 降级或替代方案

- Docker Engine 未恢复前可将 `DATABASE_PROVIDER=sqlite` 继续运行完整 Mock 演示。

### 下一步

- Engine 恢复后先验证 `docker version`，再启动项目 MySQL 并初始化。

## Docker 虚拟化支持诊断

### 已完成

- 根据 Docker Desktop UI 的 `Virtualization support not detected` 做 CPU、固件、WSL、Hypervisor 与服务只读检查。
- 确认 AMD Ryzen 9 7940H 的固件虚拟化、SLAT、VM Monitor 均为 True；WSL 2.7.8 已安装。
- 确认 Windows 11 当前 `HypervisorPresent=False`，因此 Docker WSL2 Linux Engine 无法启动；这不是数据库或 Compose 配置问题。

### 实际验证

- 执行命令：`Get-CimInstance Win32_Processor`、`Get-CimInstance Win32_ComputerSystem`、`wsl --version`、相关服务查询。
- 返回结果：硬件/BIOS 能力正常；Hypervisor 未加载；`vmcompute`、`WslService`、`hns` 运行；当前非管理员终端无法读取可选功能和 BCD。
- 是否通过：根因范围已确认；系统级修复尚未执行。

### 当前问题

- 需要用户在管理员 PowerShell 中确认 `VirtualMachinePlatform`、WSL 可选功能和 `hypervisorlaunchtype`。

### 降级或替代方案

- 系统虚拟化组件修复前继续使用 SQLite Mock，不运行 Docker MySQL。

### 下一步

- 用户提供管理员只读检查结果后，再决定是启用 Windows 功能还是恢复 Hypervisor 启动项；任何系统修改和重启由用户明确执行。

## MySQL 真实初始化与只读账号验证

### 已完成

- 确认项目 MySQL 8.4 容器在宿主机 3308 端口处于 `healthy` 状态。
- 修复 PyMySQL 参数化 SQL 中账号主机通配符 `%` 未转义导致的 `ValueError`。
- 真实初始化 `nebula_shop` 数据库，并创建仅有查询权限的 `nebula_reader` 运行账号。

### 实际验证

- 执行命令：`.\.venv\Scripts\python.exe scripts\init_database.py`
- 返回结果：MySQL 初始化成功，写入 2 个用户、6 个订单，运行权限标记为 `SELECT only`。
- 执行命令：通过只读账号运行最近 7 天失败订单查询并执行 `SHOW GRANTS FOR CURRENT_USER()`。
- 返回结果：`ORDER002=3`、`ORDER003=1`；授权仅包含 `USAGE` 和 `GRANT SELECT ON nebula_shop.*`。
- 执行命令：`.\.venv\Scripts\python.exe -m pytest -q`
- 返回结果：`23 passed, 1 deselected, 62 warnings in 57.47s`。
- 是否通过：通过。

### 当前问题

- 现有 62 条 warning 来自第三方兼容性弃用提示，不影响本次初始化和测试通过；后续需要单独升级 Starlette/httpx 测试适配及 Python 3.12 SQLite 日期适配。

### 降级或替代方案

- Docker/MySQL 不可用时仍可切换 `DATABASE_PROVIDER=sqlite` 运行 Mock 演示；本阶段已完成真实 MySQL 验证，无需降级。

### 下一步

- 按 README 继续启动 API 与执行五个演示任务；不要再次覆盖本地 `.env`。

## 前后端交互与用户系统扩展

### 已完成

- 新增独立 `app_users`、可撤销 `user_sessions`、`chat_sessions` 和 `chat_messages`，未复用或破坏业务 `users` 表。
- 实现 Argon2 密码、HttpOnly Cookie、角色权限、登录/聊天限流、会话和 Trace 所有权隔离。
- 聊天 API 复用现有 LangGraph/MCP/RAG 链路，并持久化回答、来源和 request_id。
- 创建 React 19 + TypeScript + Vite 中文工作台，包含登录、注册、概览、聊天、历史、来源、个人资料和执行记录。
- 创建 SQLite/MySQL 通用 Alembic 迁移、MySQL 最小权限 Web 账号配置脚本和交互式管理员创建脚本。

### 实际验证

- 基线命令：`.\.venv\Scripts\python.exe -m pytest -q`；结果：`23 passed, 1 deselected, 62 warnings in 38.71s`。
- 新增后端聚焦测试：`11 passed, 31 warnings`。
- 完整后端回归（含两个 Chrome 测试）：`34 passed, 1 deselected, 77 warnings in 72.98s`。
- 前端命令：`npm test`；结果：`4 passed`。
- 前端命令：`npm run build`；结果：TypeScript 与 Vite 生产构建退出 0。
- Chrome E2E：固件清理修复后复验 `1 passed in 26.19s`，使用本机 `channel="chrome"`，真实完成注册、登录、Agent 问答、来源、刷新历史、注销和路由保护；5174/8766 测试端口均已释放。
- MySQL：Alembic 迁移退出 0；Web 表事务写入/读取成功；Web 账号读取 `orders` 被拒绝。
- 是否通过：核心验收通过。

### 当前问题

- 外部真实 LLM 和语义 Embedding 仍因未配置 Key 而未验证；当前界面明确显示 Mock LLM 和 TF-IDF 降级检索。
- 页面已按路由懒加载，代码高亮仅注册四种语言；最大页面包约 311 kB，生产构建无大包 warning。
- 第三方 Starlette/SQLite 产生弃用 warning，不影响退出状态。

### 降级或替代方案

- 没有 MySQL Web 应用密码时，可将 `DATABASE_PROVIDER=sqlite` 后运行 Alembic，完成全部无 Key 前后端演示。

### 下一步

- 用户在本地 `.env` 设置独立 `MYSQL_APP_PASSWORD` 后重新运行 `scripts/provision_web_database.py`，再按 README 分别启动后端和前端。
## 第二版真实模型复验与可观测性配置

### 已完成

- 使用本地 `.env` 中更新后的 DeepSeek Key 验证 `deepseek-v4-flash` 普通生成、Pydantic 结构化路由、Direct、Database 和 Hybrid Agent 链路。
- 修正 DeepSeek JSON Output 兼容、路由工具白名单、Planner 参数 Schema 和 Hybrid 工具参数映射。
- 增加真实 MySQL 标记测试、GitHub Actions MySQL 8.4 服务容器，以及 LangSmith/OTLP 独立配置入口。

### 实际验证

- 执行命令：`.\.venv\Scripts\python.exe -m pytest tests\unit\test_observability.py tests\unit\test_llm_provider.py tests\unit\test_tool_schemas.py tests\unit\test_routing_v2.py tests\integration\test_agent.py -q`
- 返回结果：`18 passed, 15 warnings in 10.20s`；warning 为 Python 3.12 SQLite 默认日期适配器弃用提示。
- 执行命令：`.\.venv\Scripts\python.exe -m pytest tests\integration\test_mysql_runtime.py -q -m mysql -o "addopts="`
- 返回结果：`6 passed in 0.49s`。
- 执行命令：`.\.venv\Scripts\python.exe -m compileall -q app scripts tests migrations`
- 返回结果：退出码 0，无编译错误。
- 真实路由评测：首次 `8/10`；修正边界后复验 `10/10`，禁止工具误调用率 `0.0`。
- 是否通过：本地真实 LLM、MCP/MySQL Agent 链路和相关回归通过，未发生 Mock 静默降级。

### 当前问题

- LangSmith 尚未配置独立 `LANGSMITH_API_KEY`；OTLP 尚未配置 Collector/APM 接收端点，因此两项外部出站未执行。
- 当前目录尚未初始化为 Git 仓库，且本机没有 GitHub CLI；GitHub Actions 只能在用户创建并推送远程仓库后实际运行。
- 当前检索仍为明确标记的 TF-IDF 词法降级模式，不属于中文语义 Embedding 验证。

### 降级或替代方案

- LangSmith 与 OTLP 默认关闭，不影响业务 Trace、Checkpoint、真实 LLM 和本地测试。
- 远程 CI 未建立前，可继续使用本地 Docker MySQL 集成测试。

### 下一步

- 用户仅在本地 `.env` 配置 LangSmith 专用 Key 或 OTLP 接收端点后，再分别启用并执行真实出站验证。
- 按 `docs/remote-ci-guide.md` 创建 GitHub 仓库、配置三个 CI MySQL Secret 并推送代码，触发远程 CI。
## 机器学习 PDF 企业知识库导入

### 已完成

- 从用户下载目录复制截图指定的 9 份机器学习 PDF 到 `knowledge_base/enterprise`；保留下载目录原文件，未移动或删除。
- 完成 PDF 文本提取、分块、去重、索引和知识目录重建。
- 修复 PDF 正文中 `# params = 3 here` 被误当作 Markdown 标题的问题；非 Markdown 文档默认使用文件名作为标题。
- 本地运行语料已切换为 `KNOWLEDGE_CORPUS=enterprise`。

### 实际验证

- 构建命令：`.\.venv\Scripts\python.exe scripts\build_knowledge_base.py`。
- 构建结果：`mode=tfidf_fallback`、`243 chunks`、`failed=0`、`skipped=0`。
- Catalog 结果：共 17 个文档，其中 enterprise 9 个；9 个标题均与文件名对应，访问范围为 `authenticated`。
- 正式 MCP stdio 调用 `search_knowledge_base`，以 PCA 和 SVM 问题检索 enterprise 语料，均召回对应 PDF；当前检索模式明确为 `tfidf_fallback`。
- 完整 Agent 复验：真实 DeepSeek 路由为 `knowledge_base`，经 LangGraph/MCP 调用 `search_knowledge_base`，状态 `completed`、证据 `sufficient`、无 Mock 降级，引用包含《第8章 SVM支持向量机》等新导入资料。
- 聚焦测试：`3 passed in 21.20s`；`compileall` 退出码 0。

### 当前问题

- 部分 PDF 交叉引用表不规范，pypdf 输出 `Ignoring wrong pointing object` 容错警告；所有 9 份仍成功提取文本，不属于导入失败。
- 当前 `.env` 使用 TF-IDF 词法降级，尚未为这 243 个 Chunk 构建本地中文语义向量。

### 降级或替代方案

- 词法模式可立即完成精确术语检索；需要中文同义表达检索时，可切换本地 Embedding 并重建索引。

### 下一步

- 重启 FastAPI 后端以加载 `KNOWLEDGE_CORPUS=enterprise`；通过聊天页面使用“根据知识库……”形式的问题验证回答和引用。
## 数学公式与表格渲染改进

### 已完成

- 前端接入 `remark-math`、`rehype-katex`、KaTeX 和 `remark-gfm`，支持行内公式、块级公式和 GitHub Flavored Markdown 表格。
- 兼容历史回答中的 `\\(...\\)` 与 `\\[...\\]`，渲染前转换为 `$...$` 和 `$$...$$`，同时保护行内代码和围栏代码块不被改写。
- 增加表格边框、表头、斑马纹、横向滚动以及长公式横向滚动样式。
- Direct 与最终答案提示均要求真实模型生成规范 LaTeX 分隔符和逐行 Markdown 表格。

### 实际验证

- 前端命令：`npm test -- --run`，结果：`2 test files / 6 tests passed`。
- 前端命令：`npm run build`，结果：TypeScript 与 Vite 构建成功；KaTeX 字体进入构建产物。
- 后端聚焦回归：`2 passed, 15 warnings`；warning 为既有 Python 3.12 SQLite 日期适配器弃用提示。
- 真实 DeepSeek 格式复验：状态 `completed`、路由 `direct_answer`、无 Mock 降级；检测到 `$` 数学公式和 GFM 表格分隔行，未使用旧式 `\\(...\\)`/`\\[...\\]`。

### 当前问题

- Vite 提示聊天页面 Chunk 约 622 kB，超过默认 500 kB 提示阈值；不影响功能，后续可将 KaTeX/语法高亮改为按需加载。
- 已保存的旧消息无需重新生成即可兼容旧式数学分隔符；不规范且完全没有换行的伪表格仍无法可靠推断行边界。

### 降级或替代方案

- KaTeX 遇到不完整公式时保留可见错误文本，页面不会执行模型返回的脚本；原有 Markdown 清洗继续启用。

### 下一步

- 重启前端开发服务并刷新页面；重新提问可获得模型生成的规范公式和表格，历史公式也会按兼容规则重新渲染。
## README 启动流程重写与连接拒绝诊断

### 已完成

- 定位截图中的 `pymysql 2003 / WinError 10061`：后端连接 `127.0.0.1:3308` 时 Docker MySQL 尚未监听；不是密码错误。
- 将 README 重写为“首次安装与初始化”和“已经安装后的日常重新启动”两套独立流程。
- 日常启动顺序固定为 Docker Desktop → `docker compose up -d mysql` → 等待 `healthy` → Uvicorn → `/health` → Vite。
- 增加 `.env` 防覆盖、MySQL 健康等待、端口检查、停止方式、知识导入、测试命令以及 10061/1045/8000/5173/npm/Python 排障。
- 修复 MySQL 集成测试中会随日期失效的“最近七天固定计数”断言，改为验证动态时间窗口返回结构和有效计数。

### 实际验证

- Docker Compose：`nebula-shop-mysql` 为 `running (healthy)`。
- TCP：`127.0.0.1:3308` 可连接。
- FastAPI：`GET /health` 返回 `status=ok`、`database_provider=mysql`、`configuration_status=ok`。
- MySQL 专项回归：修正动态时间断言后 `6 passed in 0.57s`。
- README 自检：628 行、102 个代码围栏且成对、首次/日常/连接排障章节均存在、相对文档链接缺失数为 0。

### 当前问题

- Docker Desktop 从未运行到 Engine/MySQL healthy 可能需要几十秒；在此之前启动后端仍会得到 10061，因此不能只看 Docker Desktop 窗口已打开。
- 当前模拟订单的“最近七天”结果会随真实日期自然变化，不应永久断言 2026-07-18 验证时的固定数量。

### 降级或替代方案

- Docker/MySQL 不可用时可将本地 `.env` 明确切换为 SQLite Mock 模式；这不能作为真实 MySQL 验收。

### 下一步

- 用户以后按 README 的日常重启流程执行，确认 MySQL `healthy` 后再启动后端。

## 检索评测集与实际 Enterprise 语料对齐

### 已完成

- 保留模拟商城检索样本并拆分为 `retrieval_mock_dataset.json`。
- 新增 8 条机器学习企业语料正样本和 2 条无证据负样本，覆盖 PCA、SVM、逻辑回归、聚类、线性回归、LDA、神经网络及监督/无监督学习。
- 将评测从“单个标题关键词命中”改为文档级 Gold Set，支持一个问题对应多个相关文档。
- 分别输出文档 Recall@5、Hit Rate@5、MRR、Chunk Precision@5、无证据正确率及错误样本。
- 修复 Mock RAG 单测隐式依赖 `.env` 语料模式的问题，测试中显式指定 `corpus_type="mock"`。

### 实际验证

- 执行命令：`.\.venv\Scripts\python.exe scripts\evaluate_v2.py`
- Mock 结果：文档 Recall@5 `100%`。
- Enterprise 结果：文档 Recall@5 `87.5%`、Hit Rate@5 `87.5%`、MRR `0.875`、Chunk Precision@5 `82.5%`、无证据正确率 `50%`。
- 错误样本：逻辑回归问题未在 Top-5 召回目标文档；`ORDER002` 在 Enterprise 语料中错误召回机器学习文档。
- 回归命令：`.\.venv\Scripts\python.exe -m pytest tests\unit\test_evaluation.py tests\unit\test_rag.py -q`
- 返回结果：`4 passed in 18.29s`。
- 是否通过：评测程序和单元测试通过；检索质量存在 2 个真实失败样本，未伪造成全通过。

### 当前问题

- 当前仍为 `tfidf_fallback`，逻辑回归与神经网络存在词面重叠，目标文档排序不足。
- `LEXICAL_MIN_SCORE=0.01` 与现有 Evidence Check 偏宽松，Enterprise 无答案问题可能返回弱相关资料。
- Enterprise 数据集目前只有 10 条，适合作为基线，不足以代表生产总体质量。

### 降级或替代方案

- 在本地中文 Embedding 未启用前继续明确标记词法降级模式，并保留无证据负样本监控误召回。

### 下一步

- 扩展到至少 50–100 条人工标注样本；校准词法阈值和 Evidence Check，并分别比较 TF-IDF 与中文语义 Embedding。
