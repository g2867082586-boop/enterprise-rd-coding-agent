import { Archive, BookOpen, ChevronRight, FileText, MessageSquarePlus, PanelRightClose, Paperclip, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Modal } from "antd";
import { chatApi, systemApi } from "../api";
import { ApiError } from "../api/client";
import { ChatMessage as ChatMessageView } from "../components/ChatMessage";
import { StatusBadge } from "../components/StatusBadge";
import type { ChatAttachment, ChatSession, Message } from "../types";

const suggestions = ["用户登录接口需要哪些参数？", "ORDER002 错误应该如何排查？", "最近七天失败订单有哪些？"];

export function ChatPage() {
  const [params, setParams] = useSearchParams(); const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [active, setActive] = useState<ChatSession | null>(null); const [text, setText] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [runtime, setRuntime] = useState<Record<string, string>>({ llm_mode: "mock", retrieval_mode: "tfidf_fallback" });
  const [sourceMessage, setSourceMessage] = useState<Message | null>(null); const bottom = useRef<HTMLDivElement>(null);
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const reloadList = async () => setSessions(await chatApi.list());
  const open = async (id: string) => { setActive(await chatApi.get(id)); setParams({ session: id }); setSourceMessage(null); };
  useEffect(() => { void reloadList().then(async () => { const id = params.get("session"); if (id) await open(id); }); void systemApi.health().then(setRuntime); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [active?.messages, busy]);
  const create = async () => { const session = await chatApi.create(); await reloadList(); await open(session.id); };
  const send = async (override?: string) => {
    const content = (override ?? text).trim(); if (!content || busy) return;
    let chat = active; if (!chat) { chat = await chatApi.create(); setActive({ ...chat, messages: [] }); setParams({ session: chat.id }); }
    const optimistic: Message = { id: `temp-${Date.now()}`, role: "user", content, status: "completed", request_id: null, sources: [], metadata: {}, created_at: new Date().toISOString() };
    setActive(current => current ? { ...current, messages: [...(current.messages || []), optimistic] } : current); setText(""); setBusy(true); setError("");
    try { await chatApi.send(chat.id, content, attachments.map(item => item.id)); setAttachments([]); setActive(await chatApi.get(chat.id)); await reloadList(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "网络连接失败，请检查后端服务"); }
    finally { setBusy(false); }
  };
  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []); if (!files.length) return;
    let chat = active;
    if (!chat) { chat = await chatApi.create(); setActive({ ...chat, messages: [] }); setParams({ session: chat.id }); await reloadList(); }
    setUploading(true); setError("");
    try {
      const uploaded: ChatAttachment[] = [];
      for (const file of files.slice(0, 10 - attachments.length)) uploaded.push(await chatApi.upload(chat.id, file));
      setAttachments(current => [...current, ...uploaded]);
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "附件上传失败"); }
    finally { setUploading(false); if (fileInput.current) fileInput.current.value = ""; }
  };
  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } };
  const archive = (id: string) => { Modal.confirm({ title: "归档会话", content: "历史执行记录将继续保留，确认归档吗？", okText: "确认归档", cancelText: "取消", onOk: async () => { await chatApi.archive(id); setActive(null); setParams({}); await reloadList(); } }); };
  return <div className="chat-layout"><aside className="conversation-panel"><div className="conversation-head"><h2>知识问答</h2><button aria-label="新建会话" onClick={() => void create()}><MessageSquarePlus size={18} /></button></div><button className="new-chat" onClick={() => void create()}><Sparkles size={17} />新建会话</button><div className="conversation-list">{sessions.map(item => <button className={active?.id === item.id ? "active" : ""} key={item.id} onClick={() => void open(item.id)}><span><strong>{item.title}</strong><small>{new Date(item.last_message_at || item.created_at).toLocaleDateString("zh-CN")}</small></span><ChevronRight size={15} /></button>)}</div></aside>
    <section className="chat-main"><header><div><h1>{active?.title || "新的知识问答"}</h1><StatusBadge tone="amber">{runtime.llm_mode === "openai_compatible" ? "真实 LLM" : runtime.llm_mode === "mock_fallback" ? "Mock 降级" : "Mock LLM"}</StatusBadge><StatusBadge tone="blue">{runtime.retrieval_mode === "local" ? "中文语义检索" : runtime.retrieval_mode === "openai_compatible" ? "API 语义检索" : "TF-IDF 词法降级"}</StatusBadge></div>{active && <button className="icon-text" onClick={() => void archive(active.id)}><Archive size={15} />归档</button>}</header>
      <div className="message-scroll">{!active?.messages?.length ? <div className="chat-empty"><span><BookOpen size={28} /></span><h2>知识，从一个好问题开始</h2><p>我会检索星云商城知识库，并展示回答引用的文档来源。</p><div>{suggestions.map(item => <button key={item} onClick={() => void send(item)}>{item}<ChevronRight size={15} /></button>)}</div></div> : active.messages.map(message => <ChatMessageView key={message.id} message={message} onSources={setSourceMessage} />)}
        {busy && <div className="thinking"><span className="thinking-dots"><i /><i /><i /></span><div><strong>Agent 正在分析</strong><small>正在规划、检索知识库并整理回答…</small></div></div>}{error && <div className="chat-error" role="alert">{error}<button onClick={() => void send(active?.messages?.at(-1)?.content)}>重试</button></div>}<div ref={bottom} /></div>
      <div className="composer">{attachments.length > 0 && <div className="attachment-list">{attachments.map(item => <span key={item.id}><FileText size={14} />{item.name}<small>{Math.ceil(item.size / 1024)} KB</small><button aria-label={`移除 ${item.name}`} onClick={() => setAttachments(current => current.filter(row => row.id !== item.id))}><X size={13} /></button></span>)}</div>}<div><input ref={fileInput} type="file" multiple hidden accept=".pdf,.docx,.md,.txt,.json,.csv" onChange={e => void upload(e)} /><button className="attach-button" aria-label="添加附件" onClick={() => fileInput.current?.click()} disabled={busy || uploading}><Paperclip size={18} /></button><textarea aria-label="输入问题" value={text} onChange={e => setText(e.target.value)} onKeyDown={onKey} placeholder="输入问题；上传后输入“添加进知识库”可提交审批" maxLength={2000} disabled={busy} /><button aria-label="发送问题" onClick={() => void send()} disabled={busy || uploading || text.trim().length < 2}><Send size={18} /></button></div><small>{uploading ? "正在安全上传附件…" : `当前模式：${runtime.llm_mode} / ${runtime.retrieval_mode}。企业事实请结合引用核验。`}</small></div>
    </section>
    {sourceMessage && <aside className="source-panel"><header><div><span className="source-icon"><BookOpen size={17} /></span><div><h2>知识来源</h2><small>{sourceMessage.sources.length} 个相关片段</small></div></div><button aria-label="关闭来源" onClick={() => setSourceMessage(null)}><PanelRightClose size={18} /></button></header><div>{sourceMessage.sources.map((source, index) => <article key={`${source.source}-${index}`}><div><span>来源 {index + 1}</span><b>{Math.round(source.score * 100)}% 相关</b></div><h3>{source.title}</h3><code>{source.source}</code><p>{source.snippet}</p></article>)}</div></aside>}
  </div>;
}
