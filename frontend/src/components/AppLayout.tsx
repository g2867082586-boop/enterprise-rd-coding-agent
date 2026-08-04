import { Activity, BookOpen, CheckSquare, Database, Home, LogOut, MessageSquare, UserRound, Workflow } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { authApi } from "../api";
import { useAuth } from "../auth";

export function AppLayout() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const logout = async () => { await authApi.logout(); setUser(null); navigate("/login"); };
  const links = [
    ["/", "概览", Home], ["/chat", "知识问答", MessageSquare], ["/orders", "订单中心", Database],
    ["/traces", "执行记录", Workflow], ["/profile", "个人资料", UserRound],
  ] as const;
  const adminLinks = user?.role === "admin" ? [
    ["/knowledge-admin", "知识库管理", Database], ["/approvals", "审批中心", CheckSquare],
    ["/observability", "运行概览", Activity],
  ] as const : [];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><BookOpen size={21} /></span><div><strong>星云智库</strong><small>研发知识助手</small></div></div>
      <nav>{[...links, ...adminLinks].map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/"}><Icon size={18} />{label}</NavLink>)}</nav>
      <div className="sidebar-user"><div className="avatar">{user?.display_name.slice(0, 1)}</div><div><strong>{user?.display_name}</strong><small>{user?.role === "admin" ? "管理员" : "知识库成员"}</small></div><button aria-label="退出登录" onClick={() => void logout()}><LogOut size={17} /></button></div>
    </aside>
    <main className="main-content"><Outlet /></main>
  </div>;
}
