# 星云商城 MySQL 数据字典

`users` 表字段为 `id`、`username`、`email`、`status`、`created_at`、`last_login_at`。运行时只读 Agent 对 email 进行脱敏，不允许读取任何凭据字段。

`orders` 表字段为 `id`、`user_id`、`order_no`、`amount`、`status`、`error_code`、`created_at`、`updated_at`。联合索引 `idx_orders_status_created(status, created_at)` 支持最近失败订单统计。时间统一以 UTC 写入，展示层再转换时区。

`test_runs` 保存 pytest 执行摘要；`agent_traces` 保存审计事件。LangGraph Checkpoint 单独保存在 SQLite Checkpointer 中，`agent_traces` 不能替代 Checkpoint。

