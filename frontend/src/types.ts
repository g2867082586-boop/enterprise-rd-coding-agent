export interface User {
  id: string; username: string; email: string; display_name: string; role: "user" | "order_operator" | "admin";
  is_active: boolean; created_at: string; last_login_at: string | null;
}

export interface Source { title: string; source: string; snippet: string; score: number }
export interface Message {
  id: string; role: string; content: string; status: string; request_id: string | null;
  sources: Source[]; metadata: Record<string, unknown>; created_at: string;
}
export interface ChatSession {
  id: string; title: string; created_at: string; updated_at: string; last_message_at: string | null;
  messages?: Message[];
}
export interface AgentReply {
  message_id: string; session_id: string; request_id: string | null; status: string; answer: string;
  sources: Source[]; trace_summary: { tools: string[]; steps: number };
  runtime_mode: { llm: string; retrieval: string; database: string }; created_at: string;
}
export interface TraceSummary {
  request_id: string; question: string; created_at: string; status: string; tools: string[];
  duration_ms: number; success: boolean;
}
export interface TraceSpan {
  sequence: number; span_id: string; parent_span_id: string | null; event_type: string;
  span_name: string; node_name: string; tool_name: string | null; started_at: string | null;
  finished_at: string | null; duration_ms: number; success: boolean | null; error: string | null;
  input: unknown; output: unknown; model_info: Record<string, unknown>;
  route: string | null; route_confidence: number | null;
}
export interface TraceDetail {
  request_id: string;
  summary: {
    question: string; thread_id: string | null; status: string | null; success: boolean | null;
    started_at: string | null; finished_at: string | null; duration_ms: number;
    span_count: number; tool_count: number; tools: string[];
    errors: { sequence: number; span_name: string; error: string }[];
    model_info: Record<string, unknown>;
  };
  spans: TraceSpan[];
  raw_events: Record<string, unknown>[];
}
export interface Approval {
  id: string; thread_id: string; operation: string; risk_level: string;
  status: string; parameters: Record<string, unknown>; created_at: string; expires_at: string;
}
export interface KnowledgeDocument {
  document_id: string; title: string; document_type: string; department: string;
  version: string; updated_at: string; access_scope: string; corpus_type: string; embedding_model: string;
}
export interface ChatAttachment {
  id: string; name: string; size: number; mime_type: string; status: string;
}
export interface Order {
  order_no: string; user_id: number; amount: string; status: string; error_code: string | null;
  created_at: string; updated_at: string; version: number; note?: string | null; cancel_reason?: string | null;
}
export interface OrderPageResult {
  items: Order[]; total: number; page: number; page_size: number; pages: number;
}
export interface OrderAction {
  id: string; action_type: string; risk_level: string; status: string;
  parameters: Record<string, unknown>; expires_at: string;
}
