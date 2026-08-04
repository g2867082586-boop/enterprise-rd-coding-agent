import { ArrowLeft, ArrowRight, BookOpen, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api";
import { ApiError } from "../api/client";

export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", display_name: "", password: "", confirm: "" });
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const set = (key: string, value: string) => setForm(current => ({ ...current, [key]: value }));
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    if (form.password !== form.confirm) { setError("两次输入的密码不一致"); return; }
    if (!/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)) { setError("密码必须同时包含字母和数字"); return; }
    setBusy(true);
    try { await authApi.register({ username: form.username, email: form.email, display_name: form.display_name, password: form.password }); navigate("/login", { state: { registered: true } }); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "网络连接失败"); }
    finally { setBusy(false); }
  };
  return <div className="auth-page"><section className="auth-story register"><div className="story-content"><div className="brand light"><span className="brand-mark"><BookOpen size={21} /></span><strong>星云智库</strong></div><span className="eyebrow">SECURE BY DESIGN</span><h1>从可信知识开始<br />高效协作</h1><p>你的会话、消息和执行记录彼此隔离，密码始终以 Argon2 安全哈希保存。</p><div className="story-stat"><ShieldCheck size={22} /><span><b>安全登录</b><small>HttpOnly Cookie · 可撤销 Session</small></span></div></div></section>
    <section className="auth-form-wrap"><form className="auth-card wide" onSubmit={submit}><Link className="back-link" to="/login"><ArrowLeft size={15} />返回登录</Link><h2>创建账号</h2><p>加入企业知识工作空间</p><div className="form-grid">
      <label>用户名<input aria-label="用户名" value={form.username} onChange={e => set("username", e.target.value)} minLength={3} required /></label>
      <label>显示名称<input aria-label="显示名称" value={form.display_name} onChange={e => set("display_name", e.target.value)} required /></label>
      <label className="span-2">邮箱<input aria-label="邮箱" type="email" value={form.email} onChange={e => set("email", e.target.value)} required /></label>
      <label>密码<input aria-label="密码" type="password" value={form.password} onChange={e => set("password", e.target.value)} minLength={8} required /></label>
      <label>确认密码<input aria-label="确认密码" type="password" value={form.confirm} onChange={e => set("confirm", e.target.value)} required /></label>
    </div><small className="password-hint">至少 8 位，同时包含字母和数字，最长 128 位</small>{error && <div className="form-error" role="alert">{error}</div>}
    <button className="primary-btn" disabled={busy}>{busy ? "正在创建…" : <>创建账号<ArrowRight size={17} /></>}</button></form></section></div>;
}
