import { api, apiForm } from "./client";
import type { AgentReply, Approval, ChatAttachment, ChatSession, KnowledgeDocument, OrderAction, OrderPageResult, TraceDetail, TraceSummary, User } from "../types";

export const authApi = {
  me: () => api<User>("/api/auth/me"),
  register: (body: object) => api<User>("/api/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: object) => api<User>("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => api<void>("/api/auth/logout", { method: "POST" }),
  update: (display_name: string) => api<User>("/api/auth/me", { method: "PATCH", body: JSON.stringify({ display_name }) }),
};
export const chatApi = {
  list: () => api<ChatSession[]>("/api/chat/sessions"),
  create: () => api<ChatSession>("/api/chat/sessions", { method: "POST", body: JSON.stringify({ title: "新对话" }) }),
  get: (id: string) => api<ChatSession>(`/api/chat/sessions/${id}`),
  archive: (id: string) => api<void>(`/api/chat/sessions/${id}`, { method: "DELETE" }),
  send: (id: string, content: string, attachment_ids: string[] = []) => api<AgentReply>(`/api/chat/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ content, attachment_ids }) }),
  upload: (id: string, file: File) => {
    const body = new FormData(); body.append("file", file);
    return apiForm<ChatAttachment>(`/api/chat/sessions/${id}/attachments`, body);
  },
};
export const traceApi = {
  list: () => api<TraceSummary[]>("/api/traces"),
  get: (requestId: string) => api<TraceDetail>(`/api/traces/${requestId}`),
};
export const systemApi = { health: () => api<Record<string, string>>("/health") };
export const approvalApi = {
  list: () => api<Approval[]>("/api/approvals"),
  approve: (id: string) => api<Approval>(`/api/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ reason: "管理员批准" }) }),
  reject: (id: string) => api<Approval>(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason: "管理员拒绝" }) }),
  resume: (id: string) => api<Approval>(`/api/approvals/${id}/resume`, { method: "POST" }),
};
export const knowledgeApi = {
  list: () => api<{ retrieval_mode: string; embedding_model: string; documents: KnowledgeDocument[] }>("/api/knowledge/documents"),
  rebuild: () => api<Approval>("/api/knowledge/rebuild", { method: "POST" }),
  managed: () => api<Array<Record<string, unknown>>>("/api/knowledge/managed-documents"),
  deactivate: (id: string) => api<Record<string, unknown>>(`/api/knowledge/managed-documents/${id}/deactivate`, { method: "POST" }),
  rollback: (id: string, versionId: string) => api<Record<string, unknown>>(`/api/knowledge/managed-documents/${id}/rollback/${versionId}`, { method: "POST" }),
};
export const orderApi = {
  list: (query = "") => api<OrderPageResult>(`/api/orders${query ? `?${query}` : ""}`),
  statistics: () => api<Record<string, unknown>>("/api/orders/statistics"),
  prepare: (body: object) => api<OrderAction>("/api/order-actions", {
    method: "POST", body: JSON.stringify(body),
  }),
  confirm: (id: string, idempotencyKey: string) => api<{ id: string; status: string; result: object }>(
    `/api/order-actions/${id}/confirm`,
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
  ),
};
