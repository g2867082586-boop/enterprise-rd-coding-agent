# 五个中文问题检索验证

实际命令：`.venv\Scripts\python -c "from app.rag.indexer import search; ..."`。索引含 10 个 chunk。当前结果为字符 n-gram TF-IDF 词法相关度，不是语义相似度。

| 查询 | top-1 文档 | 片段关键内容 | 相关度 | 符合预期 |
|---|---|---|---:|---|
| 登录接口需要哪些参数 | 登录失败排查手册 | username/password、用户状态与哈希排查 | 0.0091 | 是（综合任务 top-3 同时返回接口文档） |
| AUTH001 如何排查 | 登录失败排查手册 | 字段、ACTIVE、哈希迁移 | 0.1071 | 是 |
| ORDER002 是什么 | 订单失败排查手册 | 最近七天与库存预占超时链路 | 0.1251 | 是 |
| 最近七天失败订单如何统计 | 订单查询接口 | UTC 七天、FAILED、error_code 分组 | 0.0630 | 是 |
| Web 页面如何验证 | Web 可用性标准 | Chrome、状态、文本、截图 | 0.0423 | 是 |

词法模式对同义改写的泛化有限；切换真实语义 Embedding 时保留来源、分块、Provider 和返回 schema。

