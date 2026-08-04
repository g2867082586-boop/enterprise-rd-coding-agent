import { Bot, Check, Copy, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import type { Message } from "../types";

export function normalizeMathDelimiters(content: string) {
  return content.split(/(```[\s\S]*?```|`[^`\n]*`)/g).map((part, index) => {
    if (index % 2 === 1) return part;
    return part
      .replace(/\\\[([\s\S]*?)\\\]/g, (_match, formula: string) => `\n\n$$${formula.trim()}$$\n\n`)
      .replace(/\\\((.+?)\\\)/g, (_match, formula: string) => `$${formula.trim()}$`);
  }).join("");
}

interface Submission {
  job_id?: string; approval_id?: string; status?: string; duplicate?: boolean;
}

function KnowledgeProgress({ submissions }: { submissions: Submission[] }) {
  const [jobs, setJobs] = useState<Record<string, { stage: string; progress: number; status: string; error?: string }>>({});
  useEffect(() => {
    const streams = submissions.filter(item => item.job_id).map(item => {
      const stream = new EventSource(`/api/knowledge/jobs/${item.job_id}/events`, { withCredentials: true });
      stream.addEventListener("progress", event => {
        const payload = JSON.parse((event as MessageEvent).data);
        setJobs(current => ({ ...current, [String(item.job_id)]: payload }));
        if (["completed", "failed", "cancelled"].includes(payload.status)) stream.close();
      });
      return stream;
    });
    return () => streams.forEach(stream => stream.close());
  }, [submissions.map(item => item.job_id).join(",")]);
  return <div className="knowledge-progress">{submissions.map((item, index) => {
    if (item.duplicate) return <div key={index}><strong>附件 {index + 1}</strong><span>内容已存在</span></div>;
    const job = item.job_id ? jobs[item.job_id] : undefined;
    const progress = job?.progress ?? 0;
    return <div key={item.job_id || index}><strong>知识库任务 {index + 1}</strong><span>{job?.stage || item.status || "pending_approval"} · {progress}%</span><i><b style={{ width: `${progress}%` }} /></i>{job?.error && <small>{job.error}</small>}</div>;
  })}</div>;
}

export function ChatMessage({ message, onSources }: { message: Message; onSources: (message: Message) => void }) {
  const [copied, setCopied] = useState(false);
  const renderedContent = normalizeMathDelimiters(message.content);
  const copy = async () => { await navigator.clipboard.writeText(message.content); setCopied(true); setTimeout(() => setCopied(false), 1200); };
  return <article className={`chat-message ${message.role}`}>
    <div className="message-icon">{message.role === "assistant" ? <Bot size={18} /> : <UserRound size={18} />}</div>
    <div className="message-body">
      <div className="message-meta"><strong>{message.role === "assistant" ? "星云助手" : "你"}</strong><time>{new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</time></div>
      <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeSanitize, rehypeKatex]} components={{
        code({ children, className, ...props }) {
          const match = /language-(\w+)/.exec(className || "");
          return match
            ? <pre className={`code-block language-${match[1]}`}><code>{String(children).replace(/\n$/, "")}</code></pre>
            : <code className={className} {...props}>{children}</code>;
        },
      }}>{renderedContent}</ReactMarkdown></div>
      {message.role === "assistant" && <div className="message-actions">
        <button onClick={() => void copy()}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "已复制" : "复制回答"}</button>
        {message.sources.length > 0 && <button onClick={() => onSources(message)}>查看 {message.sources.length} 个知识来源</button>}
      </div>}
      {message.role === "assistant" && Array.isArray(message.metadata.knowledge_submissions) && <KnowledgeProgress submissions={message.metadata.knowledge_submissions as Submission[]} />}
      {message.role === "assistant" && <details className="execution-details"><summary>执行详情</summary><dl><dt>路由</dt><dd>{String(message.metadata.route || "-")}</dd><dt>置信度</dt><dd>{String(message.metadata.route_confidence || "-")}</dd><dt>原因</dt><dd>{String(message.metadata.route_reason || "-")}</dd><dt>请求 ID</dt><dd>{message.request_id || "-"}</dd><dt>降级</dt><dd>{String(message.metadata.fallback_reason || "无")}</dd></dl></details>}
    </div>
  </article>;
}
