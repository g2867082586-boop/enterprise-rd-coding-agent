# HTTP API

## Web 用户与聊天 API

- `POST /api/auth/register`：注册独立 `app_users` 账号，密码使用 Argon2 哈希。
- `POST /api/auth/login`：统一凭据错误响应，设置有期限的 HttpOnly Session Cookie。
- `GET/PATCH /api/auth/me`：查看或修改当前用户显示名称。
- `POST /api/auth/logout`：撤销服务端 Session 并清除 Cookie。
- `POST/GET /api/chat/sessions`：创建或列出当前用户会话。
- `GET/DELETE /api/chat/sessions/{id}`：读取自己的会话或软归档。
- `POST /api/chat/sessions/{id}/messages`：保存问题、复用现有 LangGraph Agent、保存回答、来源和 request_id。
- `GET /api/traces`：当前用户的脱敏 Trace 摘要。
- `GET /api/traces/{request_id}`：仅在请求属于当前用户时返回脱敏节点信息。

所有聊天和用户 Trace 接口都要求 Cookie 登录；跨用户访问统一返回 404。原有 `/api/agent/run`、`/api/agent/traces/{request_id}` 和 `/api/knowledge/rebuild` 仅管理员可用。

- `GET /health`：返回服务、LLM、检索和数据库模式。
- `POST /api/agent/run`：JSON `{"query":"...","session_id":"..."}`；返回 request ID、状态、回答、来源、工具调用、Trace 摘要和运行模式。
- `GET /api/agent/traces/{request_id}`：读取独立 JSONL Trace。
- `POST /api/knowledge/rebuild`：development 环境可用；非 development 必须提供 `X-Rebuild-Token` 且与本地环境变量匹配。
- `GET /`：本地 Chrome 演示页。

PowerShell 示例：

```powershell
$body = @{query='ORDER002 是什么？'; session_id='api-demo'} | ConvertTo-Json
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/agent/run -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```
