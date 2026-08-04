# 星云商城订单查询接口

## GET /api/v1/orders/{order_no}

路径参数 `order_no` 必须是 `NS` 加 8 位数字。成功返回订单号、脱敏用户信息、金额、状态、错误码和 UTC 创建时间。状态包括 `PAID`、`PROCESSING`、`FAILED`。

`ORDER002` 表示库存预占超时：库存服务在 3 秒内未完成预占，订单进入 `FAILED`；建议检查库存锁竞争、库存服务 P95 延迟和重试幂等键。`ORDER003` 表示支付网关超时；应核对网关请求编号，不可盲目重复扣款。

订单数据存于 `orders` 表；最近七天失败统计必须按运行时 UTC 当前时间回溯七天并按 `error_code` 分组。订单测试入口为 `tests/scenarios/test_orders.py`。

