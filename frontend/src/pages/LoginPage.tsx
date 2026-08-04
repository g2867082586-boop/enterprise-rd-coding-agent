import { ArrowRight, BookOpen, LockKeyhole } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api";
import { ApiError } from "../api/client";
import { useAuth } from "../auth";

export function LoginPage() {
  const { user, setUser } = useAuth(); const navigate = useNavigate();
  const [username, setUsername] = useState(""); const [password, setPassword] = useState("");
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { if (user) navigate("/chat", { replace: true }); }, [user, navigate]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try { const loggedIn = await authApi.login({ username, password }); setUser(loggedIn); navigate("/chat"); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "网络连接失败"); }
    finally { setBusy(false); }
  };
  return <div className="auth-page"><section className="auth-story"><div className="story-content"><div className="brand light"><span className="brand-mark"><BookOpen size={21} /></span><strong>星云智库</strong></div><span className="eyebrow">ENTERPRISE KNOWLEDGE</span><h1>让企业知识<br />成为每个人的能力</h1><p>连接研发文档、业务数据与自动化工具，在一个可信赖的工作空间中获得答案。</p><div className="story-stat"><b>真实工作流</b><span>LangGraph · MCP · RAG</span></div></div></section>
    <section className="auth-form-wrap"><form className="auth-card" onSubmit={submit}><div className="auth-icon"><LockKeyhole size={22} /></div><h2>欢迎回来</h2><p>登录以继续访问企业知识库</p>
      <label>用户名或邮箱<input aria-label="用户名或邮箱" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label>
      <label>密码<input aria-label="密码" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
      {error && <div className="form-error" role="alert">{error}</div>}
      <button className="primary-btn" disabled={busy}>{busy ? <><span className="spinner" />正在登录</> : <>进入工作台<ArrowRight size={17} /></>}</button>
      <footer>还没有账号？<Link to="/register">创建账号</Link></footer></form></section></div>;
}
