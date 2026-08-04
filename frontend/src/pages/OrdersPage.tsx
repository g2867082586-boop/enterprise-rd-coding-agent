import { Database, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { orderApi } from "../api";
import { useAuth } from "../auth";
import type { Order, OrderPageResult } from "../types";


const empty: OrderPageResult = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };

export function OrdersPage() {
  const { user } = useAuth();
  const [data, setData] = useState<OrderPageResult>(empty);
  const [filters, setFilters] = useState({ order_no: "", status: "", error_code: "" });
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Order | null>(null);
  const canWrite = user?.role === "admin" || user?.role === "order_operator";
  const query = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    return params.toString();
  }, [filters]);
  const load = async () => {
    setLoading(true);
    try { setData(await orderApi.list(query)); } finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    const events = new EventSource("/api/orders/events/stream", { withCredentials: true });
    events.addEventListener("order", () => void load());
    events.addEventListener("orders_changed", () => void load());
    return () => events.close();
  }, [query]);
  const submit = (event: FormEvent) => { event.preventDefault(); void load(); };
  return <section className="page">
    <header className="page-header"><div><span className="eyebrow dark">ORDER OPERATIONS</span><h1>订单中心</h1><p>实时查询、受控变更、乐观锁与完整审计。</p></div><button className="icon-text" onClick={() => void load()}><RefreshCw size={16} />刷新</button></header>
    <form className="card order-filter" onSubmit={submit}>
      <label>订单号<input placeholder="NS00000001" value={filters.order_no} onChange={e => setFilters({ ...filters, order_no: e.target.value })} /></label>
      <label>状态<select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">全部</option><option>PROCESSING</option><option>PAID</option><option>FAILED</option><option>CANCELLED</option></select></label>
      <label>错误码<input placeholder="ORDER002" value={filters.error_code} onChange={e => setFilters({ ...filters, error_code: e.target.value })} /></label>
      <button className="primary-btn"><Search size={16} />查询</button>
    </form>
    <div className="card"><div className="section-heading"><div><h2>订单记录</h2><p>共 {data.total} 笔，数据库变化会自动刷新</p></div>{canWrite && <span className="status-badge amber">写操作需二次确认</span>}</div>
      {loading ? <div className="empty-state">正在读取最新订单…</div> : <table><thead><tr><th>订单号</th><th>用户</th><th>金额</th><th>状态</th><th>错误码</th><th>版本</th><th>更新时间</th></tr></thead><tbody>{data.items.map(order => <tr key={order.order_no} onClick={() => setSelected(order)}><td><code>{order.order_no}</code></td><td>{order.user_id}</td><td>¥{order.amount}</td><td>{order.status}</td><td>{order.error_code || "-"}</td><td>v{order.version}</td><td>{new Date(order.updated_at).toLocaleString("zh-CN")}</td></tr>)}</tbody></table>}
      {!loading && !data.items.length && <div className="empty-state"><Database size={24} />没有符合条件的订单。</div>}
    </div>
    {selected && <aside className="order-detail card"><button onClick={() => setSelected(null)}>关闭</button><h2>{selected.order_no}</h2><pre>{JSON.stringify(selected, null, 2)}</pre><p>{canWrite ? "可在聊天中输入订单操作指令，系统会生成不可变待确认动作。" : "当前账号仅有订单查询权限。"}</p></aside>}
  </section>;
}
