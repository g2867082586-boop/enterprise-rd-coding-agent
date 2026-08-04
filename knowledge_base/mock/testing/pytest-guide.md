# 星云商城 pytest 测试规范

默认命令 `pytest -q` 必须全部通过，测试需独立准备数据且不能依赖执行顺序。受控失败测试使用 `demo_failure` marker，命令为 `pytest -m demo_failure -v -o "addopts="`；该命令预期用于展示真实失败堆栈，不能计入默认回归失败。

登录测试位于 `tests/scenarios/test_login.py`，订单测试位于 `tests/scenarios/test_orders.py`。Agent 只能通过结构化参数调用 pytest，固定工作目录，使用 `shell=False`，限制超时和输出长度。

