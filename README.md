# 企业知识库、订单与研发流程 Agent

当前版本已从单机演示原型升级为可部署的小型生产架构，面向约 10–50 名用户：

- 订单结构化查询、统计、详情、受控写入、幂等确认、审计日志和实时更新通知；
- 聊天附件上传，以及在聊天中输入“添加进知识库”后发起审批和后台入库；
- Redis 分布式限流、用户并发锁和 RQ 后台任务；
- 知识文档版本、不可变索引版本、回滚/停用、中文语义与词法混合检索；
- MySQL 最小权限账户、生产环境 CSRF/Cookie 校验、存活/就绪探针；
- API、Worker、Redis、MySQL 和 Nginx 前端的 Docker Compose 部署。

生产部署和验收步骤见 [docs/production-deployment.md](docs/production-deployment.md)，接口增量见
[docs/production-api.md](docs/production-api.md)。

这是一个面向企业知识问答、业务数据分析、自动化测试和页面验证的单 Agent 原型系统。

核心链路为：

```text
React 工作台
→ FastAPI
→ LangGraph StateGraph
→ MCP Client / MCP Server
→ RAG、MySQL、pytest、Google Chrome
→ Evidence Check
→ 最终回答、Trace、Checkpoint
```

系统支持真实 OpenAI-compatible LLM，也保留无 Key 的 Mock 模式；支持本地中文 Embedding，并保留明确标记的 TF-IDF 词法降级模式。

## 先判断你应该使用哪套流程

- 从未安装或第一次在这台电脑上运行：使用“首次安装与初始化”。
- `.venv`、`frontend/node_modules`、`.env` 和数据库已经初始化：使用“日常重新启动”。
- 不确定时，先执行下面的检查，不要直接覆盖 `.env`：

```powershell
$ProjectRoot = "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
Set-Location -LiteralPath $ProjectRoot

[pscustomobject]@{
    ProjectRoot = Test-Path -LiteralPath ".\pyproject.toml"
    PythonVenv = Test-Path -LiteralPath ".\.venv\Scripts\python.exe"
    LocalEnv = Test-Path -LiteralPath ".\.env"
    FrontendPackage = Test-Path -LiteralPath ".\frontend\package.json"
    FrontendDependencies = Test-Path -LiteralPath ".\frontend\node_modules"
}
```

如果以上项目都为 `True`，通常直接使用日常重启流程。

## 运行环境

本项目主要在 Windows PowerShell 中运行，当前开发环境实际使用：

- Python 3.12；
- Node.js 与 npm；
- Docker Desktop Linux Engine；
- Docker Compose；
- Google Chrome；
- MySQL 8.4 Docker 容器；
- 项目虚拟环境 `.venv`。

项目默认通过 Playwright 的 `channel="chrome"` 使用本机 Google Chrome，不需要下载 Playwright Chromium。

## 一、首次安装与初始化

首次流程通常只执行一次。不要每次启动都重新创建虚拟环境、覆盖 `.env` 或重新初始化数据库。

### 1. 进入项目根目录

打开 PowerShell：

```powershell
$ProjectRoot = "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath ".\pyproject.toml")) {
    throw "当前目录不是项目根目录：$((Get-Location).Path)"
}
```

后端命令必须在包含 `pyproject.toml` 的项目根目录执行。

### 2. 创建 Python 虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

验证：

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -c "import fastapi, langgraph, mcp; print('Python dependencies: OK')"
```

不要在用户目录下误用另一套 `.venv`。推荐始终使用完整的相对解释器路径：

```text
.\.venv\Scripts\python.exe
```

### 3. 创建本地 `.env`

只有 `.env` 不存在时才从模板创建：

```powershell
if (-not (Test-Path -LiteralPath ".\.env")) {
    Copy-Item -LiteralPath ".\.env.example" -Destination ".\.env"
    Write-Host "已创建 .env，请编辑后再继续。"
} else {
    Write-Host ".env 已存在，不覆盖。"
}

notepad .env
```

不要反复执行无条件的：

```powershell
Copy-Item .env.example .env
```

它会覆盖已经保存的数据库密码和 API 配置。

MySQL 模式至少配置：

```env
DATABASE_PROVIDER=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3308
MYSQL_DATABASE=nebula_shop
MYSQL_ADMIN_USER=root
MYSQL_ADMIN_PASSWORD=为本项目生成的强随机密码
MYSQL_READONLY_USER=nebula_reader
MYSQL_READONLY_PASSWORD=另一个强随机密码
MYSQL_APP_USER=nebula_app
MYSQL_APP_PASSWORD=第三个强随机密码
```

这些密码用于本项目 Docker MySQL。第一次成功初始化后，不要随意修改 `MYSQL_ADMIN_PASSWORD`；Docker 数据卷中的 root 密码不会因为修改 `.env` 自动变化。

无 LLM Key 时可以使用：

```env
LLM_PROVIDER=mock
EMBEDDING_PROVIDER=lexical
ALLOW_MOCK_FALLBACK=true
```

真实 DeepSeek/OpenAI-compatible 模式示例：

```env
LLM_PROVIDER=openai_compatible
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
ALLOW_MOCK_FALLBACK=true
```

Key 只填写在本地 `.env`，不要发送到聊天、写入 Markdown 或提交到 Git。

知识语料选择：

```env
KNOWLEDGE_CORPUS=mock
```

可选值：

- `mock`：模拟业务知识库；
- `enterprise`：真实导入文档；
- `mixed`：仅用于明确的混合测试。

### 4. 启动 Docker Desktop 和 MySQL

先手动打开 Docker Desktop，等待界面显示 Engine 已运行。然后执行：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
docker compose up -d mysql
docker compose ps
```

`docker compose up -d` 只表示容器启动请求已提交，不代表 MySQL 已经可以连接。继续等待健康状态：

```powershell
$Deadline = (Get-Date).AddMinutes(3)
$MySqlHealth = ""

do {
    $MySqlHealth = docker inspect --format "{{.State.Health.Status}}" nebula-shop-mysql 2>$null
    Write-Host "MySQL health: $MySqlHealth"
    if ($MySqlHealth -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $Deadline)

if ($MySqlHealth -ne "healthy") {
    docker compose logs --tail 100 mysql
    throw "MySQL 未在 3 分钟内进入 healthy，请先处理日志中的错误。"
}
```

正常结果应包含：

```text
nebula-shop-mysql   running   healthy   0.0.0.0:3308->3306/tcp
```

还可以检查宿主机端口：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 3308
```

`TcpTestSucceeded` 应为 `True`。只有 MySQL 为 `healthy` 后才能启动后端。

本机 3306 和 3307 已被其他 MySQL 使用，因此本项目使用 3308。不要停止或修改已有数据库服务。

### 5. 首次初始化数据库

MySQL 健康后执行：

```powershell
.\.venv\Scripts\python.exe scripts\init_database.py
.\.venv\Scripts\python.exe scripts\provision_web_database.py
```

两个脚本分别负责：

- 创建模拟业务表、种子数据和只读 Agent 账号；
- 执行 Alembic 迁移并配置最小权限 Web 账号。

如需管理员账号，使用交互式命令：

```powershell
.\.venv\Scripts\python.exe scripts\create_admin.py
```

密码输入不会显示在终端，也不要把密码直接放进命令参数。

### 6. 构建知识库索引

```powershell
.\.venv\Scripts\python.exe scripts\build_knowledge_base.py
```

检查返回结果中的：

```text
failed: 0
```

当前模式如果是 `tfidf_fallback`，表示词法检索，不是语义向量检索。

### 7. 安装前端依赖

进入前端目录：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent\frontend"

if (-not (Test-Path -LiteralPath ".\package.json")) {
    throw "当前目录不是 frontend：$((Get-Location).Path)"
}

npm install
```

不能在项目根目录执行 `npm install`，因为真正的 `package.json` 位于 `frontend`。

### 8. 首次启动后端

新开一个 PowerShell，确认 MySQL 仍为 healthy，然后启动：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
docker compose ps
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

保持窗口运行。不要关闭，也不要在这个窗口继续执行前端命令。

### 9. 验证后端

再开一个 PowerShell：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

应返回 `status=ok`，并显示当前 LLM、检索和数据库模式。

### 10. 首次启动前端

再开一个 PowerShell：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent\frontend"
npm run dev
```

正常输出包含：

```text
Local: http://127.0.0.1:5173/
```

访问：

- 注册页：<http://127.0.0.1:5173/register>
- 登录页：<http://127.0.0.1:5173/login>
- 后端健康：<http://127.0.0.1:8000/health>

## 二、已经安装后的日常重新启动

日常重启不需要重新执行：

- `python -m venv`；
- `pip install -e .`；
- `npm install`；
- `scripts/init_database.py`；
- `Copy-Item .env.example .env`。

除非依赖、数据库结构或配置确实发生了变化。

### 第一步：启动 Docker Desktop

手动启动 Docker Desktop，并等待 Engine 就绪。

### 第二步：启动并等待 MySQL

第一个 PowerShell：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
docker compose up -d mysql
docker compose ps
```

如果 `STATUS` 已显示 `healthy`，继续下一步。如果是 `starting`，每隔几秒检查：

```powershell
docker compose ps
```

也可以使用：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 3308
```

必须满足：

```text
MySQL container: running / healthy
127.0.0.1:3308: TcpTestSucceeded=True
```

### 第三步：启动后端

仍在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果出现 MySQL `WinError 10061`，说明启动顺序不正确：后端已经开始连接，但 MySQL 尚未监听。停止后端，先让 MySQL 进入 healthy，再重新启动 Uvicorn。

### 第四步：确认后端健康

第二个 PowerShell：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### 第五步：启动前端

第三个 PowerShell：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent\frontend"
npm run dev
```

打开 <http://127.0.0.1:5173>。

### 日常启动顺序摘要

```text
1. Docker Desktop Engine
2. docker compose up -d mysql
3. 等待 nebula-shop-mysql healthy
4. 启动 FastAPI/Uvicorn
5. 请求 /health
6. 启动 Vite 前端
7. 打开 127.0.0.1:5173
```

## 三、什么时候需要重新安装或初始化

| 发生的变化 | 需要执行 |
| --- | --- |
| 仅电脑或项目重启 | 只执行日常重启 |
| `pyproject.toml` 或 Python 锁定依赖变化 | `.\.venv\Scripts\python.exe -m pip install -e .` |
| `frontend/package.json` 或 lock 文件变化 | 在 `frontend` 中执行 `npm install` |
| 新增或修改知识文档 | 重新执行 `scripts/build_knowledge_base.py`，并重启后端 |
| 新增 Alembic migration | 执行 `scripts/provision_web_database.py` 或 `alembic upgrade head` |
| 修改 `.env` | 重启后端；数据库端口或容器变量变化时也要检查容器配置 |
| 删除 Docker 数据卷并重新建库 | 重新执行数据库初始化；这是破坏性操作，不要在有数据时执行 |

## 四、常见连接拒绝与排查

### 1. MySQL：`WinError 10061` / `Can't connect ... 127.0.0.1`

含义：目标端口没有 MySQL 接受连接。不是密码错误。

执行：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
docker compose ps
Test-NetConnection -ComputerName 127.0.0.1 -Port 3308
docker compose logs --tail 100 mysql
```

处理顺序：

1. 打开 Docker Desktop；
2. 等待 Engine 运行；
3. 执行 `docker compose up -d mysql`；
4. 等到 `healthy`；
5. 重新启动后端。

### 2. MySQL：`1045 Access denied`

含义：端口上确实有 MySQL，但账号或密码不匹配。

检查：

- 是否误连了 3306/3307 的现有 MySQL；
- `.env` 是否被模板覆盖；
- 是否在数据卷初始化后修改了 root 密码；
- 容器是否确实映射到 3308。

不要删除数据卷来绕过密码问题，除非明确确认其中没有需要保留的数据。

### 3. 后端：访问 `127.0.0.1:8000` 被拒绝

说明 Uvicorn 没有运行或已经因启动错误退出。查看后端 PowerShell 的完整报错，并重新运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4. 前端：访问 `127.0.0.1:5173` 被拒绝

说明 Vite 没有运行。进入 `frontend` 后执行：

```powershell
npm run dev
```

### 5. npm：`ENOENT ... package.json`

说明在错误目录运行了 npm。执行：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent\frontend"
Test-Path -LiteralPath ".\package.json"
npm run dev
```

`Test-Path` 应返回 `True`。

### 6. Python：找不到脚本或 `No module named pytest`

先检查：

```powershell
Get-Location
Test-Path -LiteralPath ".\.venv\Scripts\python.exe"
Test-Path -LiteralPath ".\scripts\demo.py"
```

确保位于项目根目录，并使用项目自己的 `.venv`。

## 五、停止项目

停止前端和后端：分别在对应 PowerShell 窗口按 `Ctrl+C`。

停止项目 MySQL 容器：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
docker compose stop mysql
```

再次启动时使用：

```powershell
docker compose up -d mysql
```

`docker compose down` 会删除容器和网络，但默认保留命名数据卷。不要执行 `docker compose down -v`，它会删除项目 MySQL 数据卷。

## 六、导入企业知识文档

支持：

- Markdown；
- TXT；
- 可提取文字的 PDF；
- DOCX；
- JSON；
- CSV。

将文件复制到：

```text
knowledge_base/enterprise
```

然后在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\build_knowledge_base.py
```

这一步会执行文本提取、清洗、分块、去重、元数据登记、索引和 Catalog 更新。仅复制文件而不重建索引，聊天系统不会使用新内容。

扫描版 PDF 当前不执行 OCR，会在导入报告中标记无法提取。

使用企业文档时确认：

```env
KNOWLEDGE_CORPUS=enterprise
```

修改 `.env` 或重建索引后，重新启动后端。

## 七、测试与验收命令

后端默认回归：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
.\.venv\Scripts\python.exe -m pytest -q
```

正式 MCP stdio：

```powershell
.\.venv\Scripts\python.exe scripts\mcp_smoke.py
```

MySQL 专项：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_mysql_runtime.py -q -m mysql -o "addopts="
```

前端测试和构建：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent\frontend"
npm test -- --run
npm run build
```

Google Chrome E2E：

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
.\.venv\Scripts\python.exe -m pytest tests\browser\test_web_e2e.py -q
```

固定演示任务：

```powershell
.\.venv\Scripts\python.exe scripts\demo.py
```

受控失败测试会故意返回非零退出码：

```powershell
.\.venv\Scripts\python.exe -m pytest -m demo_failure -v -o "addopts="
```

## 八、核心能力

- 真实 LangGraph `StateGraph`、条件边、有限规划与重规划、Checkpointer、`thread_id`；
- 正式 MCP Python SDK stdio Server/Client；
- 八类路由：直接回答、知识库、数据库、测试、浏览器、代码仓库、Hybrid、澄清；
- MySQL 只读查询、SQL AST、表白名单、LIMIT 和超时；
- pytest 受控执行与结果分析；
- Playwright `channel="chrome"` 页面验证和真实截图；
- Markdown/GFM、KaTeX 数学公式和代码高亮；
- React 用户系统、聊天历史、来源、Trace、审批与管理员工作台；
- 独立业务 Trace 与 LangGraph Checkpoint；
- Mock LLM、真实 OpenAI-compatible LLM、本地 Embedding 与词法降级；
- 企业文档导入、权限过滤、Evidence Check 和引用。
- 隔离 Coding Agent：detached Git worktree、代码检索/读取、统一 diff 校验与应用、
  pytest 验证、失败反馈重试、Git diff 审查及显式工作区清理。

## 九、目录结构

```text
app/                    FastAPI、Agent、Coding Agent、MCP、RAG、数据库、安全和 Trace
frontend/               React、TypeScript、Vite、KaTeX 和前端测试
knowledge_base/mock/     模拟业务资料
knowledge_base/enterprise/ 企业导入资料
knowledge_base/catalog/  轻量知识目录
migrations/             SQLite/MySQL Alembic migration
scripts/                初始化、索引、验证、评测和演示脚本
tests/                  unit、integration、browser、evaluation、scenarios
data/                   本地数据库、索引、Checkpoint、Trace、截图
docs/                   架构、安全、API、进度和验收文档
```

## 十、安全边界与运行状态

- `.env`、数据库密码和 API Key 不得提交；
- Agent 业务数据库账号仅有 `SELECT`；
- Web 账号只操作 Web 用户与聊天表；
- SQL、命令、URL、文档范围和工具参数由代码策略校验，不由 LLM 决定；
- Coding Agent 生成的补丁只能进入隔离 worktree，不允许直接修改主工作区；
- 高风险知识库重建通过审批工作流；
- Mock、真实模型和降级状态必须在 API、前端和 Trace 中明确显示；
- TF-IDF 只能称为词法检索，不能称为语义 Embedding。

当前机器的实际验证与外部未验证项见：

- [V2 最终验收](docs/final-acceptance-v2.md)
- [项目进度与真实验证记录](docs/progress.md)
- [安全设计](docs/security.md)
- [远程 CI 指南](docs/remote-ci-guide.md)
- [Coding Agent 评测](docs/coding-agent-evaluation.md)
