import { AtSign, CalendarDays, Save, ShieldCheck, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { authApi } from "../api";
import { useAuth } from "../auth";

export function ProfilePage() {
  const { user, setUser } = useAuth(); const [name, setName] = useState(user?.display_name || "");
  const [saved, setSaved] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); const updated = await authApi.update(name); setUser(updated); setSaved(true); setTimeout(() => setSaved(false), 1600); };
  return <div className="page narrow"><header className="page-header"><div><span className="eyebrow dark">ACCOUNT</span><h1>个人资料</h1><p>管理你的基本账号信息</p></div></header><section className="profile-card"><div className="profile-banner"><div className="large-avatar">{user?.display_name.slice(0, 1)}</div><div><h2>{user?.display_name}</h2><span><ShieldCheck size={15} />{user?.role === "admin" ? "管理员" : "普通用户"}</span></div></div><form onSubmit={submit}><label><span><UserRound size={16} />用户名</span><input value={user?.username || ""} disabled /></label><label><span><AtSign size={16} />邮箱</span><input value={user?.email || ""} disabled /></label><label><span><UserRound size={16} />显示名称</span><input aria-label="显示名称" value={name} onChange={e => setName(e.target.value)} maxLength={100} /></label><label><span><CalendarDays size={16} />注册时间</span><input value={user ? new Date(user.created_at).toLocaleString("zh-CN") : ""} disabled /></label><button className="primary-btn" disabled={!name.trim()}><Save size={16} />{saved ? "已保存" : "保存更改"}</button></form></section></div>;
}
