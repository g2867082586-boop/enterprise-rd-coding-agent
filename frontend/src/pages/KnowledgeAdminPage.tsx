import { useEffect, useState } from "react";
import { knowledgeApi } from "../api";
import type { KnowledgeDocument } from "../types";

export function KnowledgeAdminPage() {
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]); const [mode, setMode] = useState(""); const [message, setMessage] = useState("");
  const [managed, setManaged] = useState<Array<Record<string, unknown>>>([]);
  const load = async () => {
    const [data, lifecycle] = await Promise.all([knowledgeApi.list(), knowledgeApi.managed()]);
    setDocs(data.documents); setManaged(lifecycle); setMode(`${data.retrieval_mode} / ${data.embedding_model || "未建立"}`);
  };
  useEffect(() => { void load(); }, []);
  const rebuild = async () => { const approval = await knowledgeApi.rebuild(); setMessage(`已创建审批 ${approval.id}，未批准前不会重建。`); };
  const deactivate = async (id: string) => { await knowledgeApi.deactivate(id); setMessage("文档已停用，请申请重建以发布新索引。"); await load(); };
  const rollback = async (id: string, versionId: string) => { await knowledgeApi.rollback(id, versionId); setMessage("版本已切换，请申请重建以原子发布。"); await load(); };
  return <section className="page"><header><div><h1>知识库管理</h1><p>当前索引：{mode}</p></div><button onClick={() => void rebuild()}>申请重建企业索引</button></header>{message && <p>{message}</p>}
    {managed.length > 0 && <div className="card"><div className="section-heading"><div><h2>文档生命周期</h2><p>审批上传、版本、停用和回滚</p></div></div><table><thead><tr><th>标题</th><th>部门/权限</th><th>状态</th><th>版本</th><th>操作</th></tr></thead><tbody>{managed.map(row => {
      const versions = (row.versions || []) as Array<Record<string, unknown>>;
      return <tr key={String(row.id)}><td>{String(row.title)}</td><td>{String(row.department)} / {String(row.access_scope)}</td><td>{String(row.status)}</td><td>{versions.map(version => `v${String(version.version)}`).join(", ") || "-"}</td><td><button onClick={() => void deactivate(String(row.id))}>停用</button>{versions.filter(version => String(version.id) !== String(row.active_version_id)).slice(0, 1).map(version => <button key={String(version.id)} onClick={() => void rollback(String(row.id), String(version.id))}>回滚 v{String(version.version)}</button>)}</td></tr>;
    })}</tbody></table></div>}
    <div className="card"><table><thead><tr><th>标题</th><th>语料</th><th>部门</th><th>版本</th><th>更新时间</th></tr></thead><tbody>{docs.map(doc => <tr key={doc.document_id}><td>{doc.title}</td><td>{doc.corpus_type}</td><td>{doc.department}</td><td>{doc.version}</td><td>{doc.updated_at}</td></tr>)}</tbody></table></div></section>;
}
