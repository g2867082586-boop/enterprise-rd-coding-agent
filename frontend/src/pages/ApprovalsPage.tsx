import { useEffect, useState } from "react";
import { approvalApi } from "../api";
import type { Approval } from "../types";

export function ApprovalsPage() {
  const [rows, setRows] = useState<Approval[]>([]); const load = async () => setRows(await approvalApi.list());
  useEffect(() => { void load(); }, []);
  const act = async (id: string, action: "approve" | "reject" | "resume") => { await approvalApi[action](id); await load(); };
  return <section className="page"><header><div><h1>审批中心</h1><p>高风险操作仅能使用服务端保存的原始参数恢复。</p></div></header><div className="card"><table><thead><tr><th>操作</th><th>风险</th><th>状态</th><th>创建时间</th><th>处理</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{row.operation}</td><td>{row.risk_level}</td><td>{row.status}</td><td>{new Date(row.created_at).toLocaleString("zh-CN")}</td><td>{row.status === "pending" && <><button onClick={() => void act(row.id, "approve")}>批准</button><button onClick={() => void act(row.id, "reject")}>拒绝</button></>}{row.status === "approved" && <button onClick={() => void act(row.id, "resume")}>恢复执行</button>}</td></tr>)}</tbody></table></div></section>;
}
