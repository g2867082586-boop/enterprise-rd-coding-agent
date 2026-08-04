import { useEffect, useState } from "react";
import { systemApi, traceApi } from "../api";
import type { TraceSummary } from "../types";

export function ObservabilityPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]); const [health, setHealth] = useState<Record<string, string>>({});
  useEffect(() => { void Promise.all([traceApi.list(), systemApi.health()]).then(([t, h]) => { setTraces(t); setHealth(h); }); }, []);
  const successes = traces.filter(item => item.success).length;
  return <section className="page"><header><div><h1>运行概览</h1><p>业务 Trace 摘要；OpenTelemetry 与 LangSmith 为独立可选链路。</p></div></header><div className="stat-grid"><article><strong>{traces.length}</strong><span>请求数</span></article><article><strong>{traces.length ? Math.round(successes / traces.length * 100) : 0}%</strong><span>成功率</span></article><article><strong>{health.llm_mode || "-"}</strong><span>LLM 模式</span></article><article><strong>{health.retrieval_mode || "-"}</strong><span>检索模式</span></article></div></section>;
}
