import { ArrowRight, BookOpenCheck, Database, MessageSquarePlus, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { chatApi, systemApi } from "../api";
import { useAuth } from "../auth";
import { StatusBadge } from "../components/StatusBadge";
import type { ChatSession } from "../types";

export function DashboardPage() {
  const { user } = useAuth(); const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [health, setHealth] = useState<Record<string, string>>({});
  useEffect(() => { void Promise.all([chatApi.list(), systemApi.health()]).then(([s, h]) => { setSessions(s); setHealth(h); }); }, []);
  return <div className="page"><header className="page-header"><div><span className="eyebrow dark">KNOWLEDGE WORKSPACE</span><h1>你好，{user?.display_name}</h1><p>今天想从企业知识中了解什么？</p></div><StatusBadge tone="green">Agent 服务在线</StatusBadge></header>
    <section className="hero-card"><div><span className="hero-icon"><Sparkles size={23} /></span><h2>向星云助手提问</h2><p>检索企业知识库，联动业务数据和研发工具，回答会附带可核验来源。</p><Link className="light-btn" to="/chat"><MessageSquarePlus size={17} />开始新问答<ArrowRight size={16} /></Link></div><div className="orb" /></section>
    <div className="stat-grid"><article><Database /><div><span>数据库模式</span><strong>{health.database_provider === "mysql" ? "真实 MySQL" : "SQLite Mock"}</strong></div></article><article><BookOpenCheck /><div><span>检索模式</span><strong>TF-IDF 词法检索</strong></div></article><article><Sparkles /><div><span>推理模式</span><strong>{health.llm_mode === "mock" ? "Mock LLM" : health.llm_mode || "读取中"}</strong></div></article></div>
    <section className="section-card"><div className="section-heading"><div><h2>最近会话</h2><p>继续之前的知识探索</p></div><Link to="/chat">查看全部<ArrowRight size={15} /></Link></div>{sessions.length ? <div className="recent-list">{sessions.slice(0, 4).map(item => <Link key={item.id} to={`/chat?session=${item.id}`}><span className="list-icon"><MessageSquarePlus size={17} /></span><div><strong>{item.title}</strong><small>{new Date(item.last_message_at || item.created_at).toLocaleString("zh-CN")}</small></div><ArrowRight size={16} /></Link>)}</div> : <div className="empty-state">暂无历史会话，从第一个问题开始吧。</div>}</section>
  </div>;
}
