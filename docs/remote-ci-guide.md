# GitHub 远程 CI 运行指南

当前目录还不是 Git 仓库，且本机没有 GitHub CLI。CI 文件已位于 `.github/workflows/ci.yml`，需推送到 GitHub 后由 GitHub Actions 运行。

## 1. 在 GitHub 网页创建空仓库

不要初始化 README、License 或 `.gitignore`，记下 GitHub 显示的仓库 HTTPS 地址。

## 2. 确认本地敏感文件不会提交

```powershell
Set-Location -LiteralPath "D:\AI Agent+MCP从0到1\enterprise-rd-agent"
Select-String -Path .gitignore -Pattern '^\.env$'
```

## 3. 初始化并推送

```powershell
git init
git branch -M main
git add .
git status
git commit -m "Enterprise R&D Agent v2"
git remote add origin https://github.com/<YOUR_ACCOUNT>/<YOUR_REPOSITORY>.git
git push -u origin main
```

`git status` 中不应出现 `.env`、`data/`中的本地数据库、Trace 或 Checkpoint。如果出现，不要推送。

## 4. 在 GitHub 配置 CI Secrets

进入仓库 `Settings -> Secrets and variables -> Actions -> New repository secret`，创建三个彼此不同的强随机密码：

- `CI_MYSQL_ROOT_PASSWORD`
- `CI_MYSQL_READONLY_PASSWORD`
- `CI_MYSQL_APP_PASSWORD`

这些只是 GitHub Runner 中一次性 MySQL 容器密码，不要使用本地生产密码。CI 不需要 LLM Key，它使用 Mock LLM 做确定性回归。

## 5. 运行与手动重跑

首次 `push` 会自动触发。在 GitHub 仓库打开 `Actions -> test` 即可查看。当前工作流已经包含 `workflow_dispatch`，也可以在该页面点击 `Run workflow` 手动运行。

CI 会真实启动隔离的 MySQL 8.4，执行迁移和种子数据，验证只读账号/禁止写入/SQL 防护/LIMIT，运行 SQLite 回归、前端测试和 Google Chrome E2E。
