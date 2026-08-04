# 生产功能 API

所有接口使用登录 Session Cookie。生产环境的 `POST/PATCH/DELETE` 还需要携带登录时下发的
CSRF Cookie 对应的 `X-CSRF-Token`。

## 订单

- `GET /api/orders`：按订单号、用户、状态、错误码、日期和金额过滤，支持分页排序。
- `GET /api/orders/statistics`：返回订单状态和时间范围统计。
- `GET /api/orders/{order_no}`：订单详情。
- `GET /api/orders/events/stream`：SSE 实时变化通知。
- `POST /api/order-actions`：准备订单写操作，必须提供幂等键。
- `POST /api/order-actions/{id}/confirm`：显式确认后执行。

支持的动作包括创建、更新状态、修改备注和取消。普通用户只读；操作员可执行低/中风险动作；
取消属于高风险动作，必须由管理员确认。并发更新使用订单 `version` 字段进行乐观锁控制。

## 聊天附件与知识库

- `POST /api/chat/sessions/{session_id}/attachments`：`multipart/form-data` 上传附件。
- `POST /api/chat/sessions/{session_id}/messages`：消息可携带 `attachment_ids`。
- 在有附件的聊天中输入“添加进知识库”，系统会创建知识文档版本、入库任务和管理员审批。
- `GET /api/knowledge/jobs/{id}`：任务状态。
- `GET /api/knowledge/jobs/{id}/events`：SSE 进度。
- `GET /api/knowledge/managed-documents`：管理员查看文档与版本。
- `POST /api/knowledge/managed-documents/{id}/deactivate`：停用。
- `POST /api/knowledge/managed-documents/{id}/rollback/{version_id}`：选择历史版本。

上传采用扩展名、MIME 和文件签名联合校验，计算 SHA-256 去重，先进入隔离目录，再由 Worker
解析。PDF 支持页数限制和扫描件 OCR 回退。索引以不可变版本保存并原子切换活动版本。

## 兼容功能

原有 LangGraph、MCP stdio、RAG、pytest、Chrome/Playwright、审批、Trace 和 Checkpoint
接口继续保留。Agent 的订单写入工具只负责创建待确认动作，不能绕过服务端角色和确认规则。
