# 安全设计

## Web 身份与数据隔离

- 密码使用 Argon2id，不保存或记录明文、MD5/SHA1 或裸 SHA-256 密码。
- 服务端 Session Token 使用密码学随机数生成，数据库只保存 SHA-256 哈希；Cookie 为 HttpOnly、SameSite=Lax、有期限，HTTPS 环境通过配置启用 Secure。
- 登录失败统一返回“用户名或密码错误”；注册、登录与聊天均有限流，单用户只允许一个 Agent 问题同时运行。
- 聊天会话、消息和 Trace 均校验用户归属；跨用户资源返回 404，普通用户不能调用知识库重建或旧版原始 Trace。
- 前端请求统一携带 Cookie，不使用 localStorage 保存长期 Token；Markdown 经 `rehype-sanitize` 清洗，代码高亮不执行返回内容。
- MySQL Web 账号不能查询 `orders/users` 等业务表，业务 Agent 仍使用独立只读账号。

数据库：SQLGlot AST 解析；拒绝多语句、写节点、未知表、危险函数及动态 LIMIT；自动上限；SQLAlchemy 参数绑定；email 脱敏；MySQL 运行账号由初始化脚本撤销其他权限后只授予 `SELECT`。管理员账号只用于初始化，密码只读 `.env`。

终端：命令与参数分开验证，只允许 python/pytest/ruff；固定项目根目录；`shell=False`；stdin 关闭；拒绝管道、重定向、命令替换及目录逃逸；设置 120 秒硬上限和 12,000 字符输出上限。

浏览器：仅 http/https；默认仅 localhost/127.0.0.1；拒绝 URL 凭据；`accept_downloads=False`；超时；无敏感表单/支付功能；始终关闭 Page/Context/Browser。

Agent：工具参数由 MCP schema/Pydantic 类型约束；知识文档只能作为资料，不能覆盖安全规则；迭代、工具次数和递归均有上限。写库、改代码、删文件、外部站点/消息等计划会进入 `human_approval` 预留节点；当前 MVP 不实现这些写工具。

Trace：敏感键统一替换为 `***`，长值截断；不记录环境变量、密码、Cookie、完整令牌。
