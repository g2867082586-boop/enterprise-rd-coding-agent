import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Copy,
  Database,
  FileJson,
  GitBranch,
  Search,
  Workflow,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { traceApi } from "../api";
import type { TraceDetail, TraceSpan, TraceSummary } from "../types";

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value ?? {}, null, 2)}</pre>;
}

function modelLabel(modelInfo?: Record<string, unknown> | null) {
  const provider = String(modelInfo?.llm_provider || "-");
  const model = String(modelInfo?.llm_model || "-");
  return `${provider} / ${model}`;
}

function normalizeTraceDetail(raw: TraceDetail | { request_id: string; events?: Record<string, unknown>[] }): TraceDetail {
  if ("summary" in raw && "spans" in raw) return raw;
  const events = raw.events || [];
  const spans = events.map((event, index) => ({
    sequence: Number(event.sequence || index + 1),
    span_id: String(event.span_id || `legacy-${index + 1}`),
    parent_span_id: (event.parent_span_id as string | null) || null,
    event_type: String(event.event_type || "span"),
    span_name: String(event.span_name || event.node_name || `event_${index + 1}`),
    node_name: String(event.node_name || event.span_name || `event_${index + 1}`),
    tool_name: (event.tool_name as string | null) || null,
    started_at: (event.started_at as string | null) || (event.recorded_at as string | null) || null,
    finished_at: (event.finished_at as string | null) || null,
    duration_ms: Number(event.duration_ms || 0),
    success: typeof event.success === "boolean" ? event.success : null,
    error: (event.error as string | null) || null,
    input: event.input || { tool_arguments: event.tool_arguments || {} },
    output: event.output || event.tool_result_summary || event,
    model_info: (event.model_info as Record<string, unknown>) || {},
    route: (event.route as string | null) || null,
    route_confidence: (event.route_confidence as number | null) || null,
  }));
  return {
    request_id: raw.request_id,
    summary: {
      question: String(events.find(event => event.user_query)?.user_query || ""),
      thread_id: null,
      status: null,
      success: spans.every(span => span.success !== false),
      started_at: spans[0]?.started_at || null,
      finished_at: spans.at(-1)?.finished_at || null,
      duration_ms: spans.reduce((total, span) => total + span.duration_ms, 0),
      span_count: spans.length,
      tool_count: new Set(spans.map(span => span.tool_name).filter(Boolean)).size,
      tools: Array.from(new Set(spans.map(span => span.tool_name).filter(Boolean))) as string[],
      errors: spans.filter(span => span.error).map(span => ({ sequence: span.sequence, span_name: span.span_name, error: span.error || "" })),
      model_info: {},
    },
    spans,
    raw_events: events,
  };
}

function SpanCard({ span, active, onClick }: { span: TraceSpan; active: boolean; onClick: () => void }) {
  const ok = span.success === false ? "failed" : span.success === true ? "success" : "pending";
  return (
    <button className={`span-card ${active ? "active" : ""}`} onClick={onClick}>
      <span className={`span-status ${ok}`}>{span.success === false ? <XCircle size={14} /> : <CheckCircle2 size={14} />}</span>
      <span>
        <strong>{span.sequence}. {span.span_name}</strong>
        <small>{span.tool_name || span.event_type} · {span.duration_ms} ms</small>
      </span>
      <ChevronRight size={15} />
    </button>
  );
}

export function TracePage() {
  const [items, setItems] = useState<TraceSummary[]>([]);
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [activeSpan, setActiveSpan] = useState<TraceSpan | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState("");

  useEffect(() => { void traceApi.list().then(setItems); }, []);

  const filtered = useMemo(
    () => items.filter(item =>
      item.question.toLowerCase().includes(query.toLowerCase()) || item.request_id.includes(query)
    ),
    [items, query],
  );

  async function openTrace(requestId: string) {
    setLoadingDetail(true);
    setDetailError("");
    try {
      const next = normalizeTraceDetail(await traceApi.get(requestId));
      setDetail(next);
      setActiveSpan(next.spans[0] || null);
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "Trace detail load failed");
    } finally {
      setLoadingDetail(false);
    }
  }

  const selected = activeSpan || detail?.spans[0] || null;

  return (
    <div className="page trace-page">
      <header className="page-header">
        <div>
          <span className="eyebrow dark">AGENT OBSERVABILITY</span>
          <h1>Agent 链路追踪</h1>
          <p>查看完整 Trace、Span 调用顺序、输入输出、耗时、错误和模型配置。</p>
        </div>
      </header>

      <section className="section-card">
        <div className="trace-toolbar">
          <div><Search size={16} /><input aria-label="搜索执行记录" placeholder="搜索问题或 request_id" value={query} onChange={e => setQuery(e.target.value)} /></div>
          <span>共 {filtered.length} 条</span>
        </div>
        {filtered.length ? (
          <div className="trace-table">
            <div className="trace-row head"><span>问题与请求</span><span>工具</span><span>耗时</span><span>状态</span></div>
            {filtered.map(item => (
              <button className="trace-row trace-clickable" key={item.request_id} onClick={() => void openTrace(item.request_id)}>
                <span><strong>{item.question || "知识库问答"}</strong><code>{item.request_id}</code><small>{new Date(item.created_at).toLocaleString("zh-CN")}</small></span>
                <span className="tool-tags">{item.tools.length ? item.tools.map(tool => <i key={tool}><Workflow size={12} />{tool}</i>) : <i>无工具</i>}</span>
                <span><Clock3 size={14} />{item.duration_ms} ms</span>
                <span className={item.success ? "success" : "failed"}>{item.success ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{item.status}</span>
              </button>
            ))}
          </div>
        ) : <div className="empty-state">还没有执行记录，完成一次知识问答后会显示在这里。</div>}
      </section>

      {detailError && <div className="trace-error"><AlertTriangle size={16} />{detailError}</div>}

      {detail && (
        <section className="trace-detail">
          <div className="trace-summary">
            <article><GitBranch size={18} /><span>Span</span><strong>{detail.summary.span_count}</strong></article>
            <article><Database size={18} /><span>工具调用</span><strong>{detail.summary.tool_count}</strong></article>
            <article><Clock3 size={18} /><span>总耗时</span><strong>{detail.summary.duration_ms} ms</strong></article>
            <article><FileJson size={18} /><span>模型</span><strong>{modelLabel(detail.summary.model_info)}</strong></article>
          </div>
          <div className="trace-detail-grid">
            <aside className="span-list">
              <header>
                <div><h2>调用顺序</h2><small>{detail.request_id}</small></div>
                <button aria-label="复制 request id" onClick={() => void navigator.clipboard.writeText(detail.request_id)}><Copy size={16} /></button>
              </header>
              {detail.spans.map(span => <SpanCard key={`${span.sequence}-${span.span_id}`} span={span} active={selected?.sequence === span.sequence} onClick={() => setActiveSpan(span)} />)}
            </aside>
            <main className="span-detail">
              {loadingDetail && <div className="empty-state">正在载入 Trace 详情...</div>}
              {selected && !loadingDetail && (
                <>
                  <header>
                    <div>
                      <span className="eyebrow dark">{selected.event_type}</span>
                      <h2>{selected.sequence}. {selected.span_name}</h2>
                      <p>{selected.tool_name ? `工具：${selected.tool_name}` : `节点：${selected.node_name}`}</p>
                    </div>
                    <span className={selected.success === false ? "failed" : "success"}>{selected.success === false ? <XCircle size={17} /> : <CheckCircle2 size={17} />}{selected.success === false ? "失败" : "完成"}</span>
                  </header>
                  <div className="span-metrics">
                    <span>Span ID <code>{selected.span_id}</code></span>
                    <span>Parent <code>{selected.parent_span_id || "-"}</code></span>
                    <span>耗时 <code>{selected.duration_ms} ms</code></span>
                    <span>模型 <code>{modelLabel(selected.model_info)}</code></span>
                  </div>
                  {selected.error && <div className="trace-error"><AlertTriangle size={16} />{selected.error}</div>}
                  <div className="io-grid">
                    <section><h3>输入</h3><JsonBlock value={selected.input} /></section>
                    <section><h3>输出</h3><JsonBlock value={selected.output} /></section>
                  </div>
                </>
              )}
            </main>
          </div>
        </section>
      )}
    </div>
  );
}
