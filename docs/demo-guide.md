# 演示与验收指南

先进入项目根目录，再初始化并启动 API（占位路径需替换）：

```powershell
$ProjectRoot = "D:\path\to\enterprise-rd-agent"
Set-Location -LiteralPath $ProjectRoot
.\.venv\Scripts\python.exe scripts\init_database.py
.\.venv\Scripts\python.exe scripts\build_knowledge_base.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开窗口后再次进入同一项目目录，再运行 `.\.venv\Scripts\python.exe scripts\demo.py`。五项依次为登录知识问答、最近七天失败订单、登录受控失败测试、Chrome 首页验证、综合任务。受控失败会真实返回 pytest exit code 1，但属于预设分析材料；默认回归仍应全通过。

MySQL：Docker daemon 可用后，在本地 `.env` 设置 `DATABASE_PROVIDER=mysql`、`MYSQL_PORT=3308`，并填写管理员和独立只读账号密码，再运行 `docker compose up -d mysql` 和初始化脚本。`.env` 已存在时不得再次用 `.env.example` 覆盖。当前机器 3306 与 3307 均有原生 `mysqld`，项目映射 3308，不应停止或修改现有服务。

停止：前台 uvicorn 使用 Ctrl+C；Docker 项目服务使用 `docker compose down`（不要加 `-v`，以免删除数据卷）。
