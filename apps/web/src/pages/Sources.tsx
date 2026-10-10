import { useState } from "react";
import { api } from "../api";
import { Badge, Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type Source = { id: number; name: string; url: string; type: string; lang: string; enabled: boolean; note: string | null };

export default function Sources() {
  const { data, loading, error, reload } = useFetch<{ items: Source[] }>("/api/v1/news-sources");
  const [form, setForm] = useState({ name: "", url: "", type: "rss", lang: "en" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [testing, setTesting] = useState<number | null>(null);

  async function create() {
    try {
      await api.post("/api/v1/news-sources", form);
      setMsg({ ok: true, text: "已添加" });
      setForm({ name: "", url: "", type: "rss", lang: "en" });
      void reload();
    } catch (e: any) { setMsg({ ok: false, text: e.message }); }
  }
  async function toggle(s: Source) {
    try { await api.patch(`/api/v1/news-sources/${s.id}`, { enabled: !s.enabled }); void reload(); }
    catch (e: any) { setMsg({ ok: false, text: e.message }); }
  }
  async function test(s: Source) {
    setTesting(s.id);
    try {
      const r = await api.post<{ ok: boolean; count?: number; error?: string }>(`/api/v1/news-sources/${s.id}/test`);
      setMsg({ ok: r.ok, text: r.ok ? `${s.name}：可达，${r.count} 条` : `${s.name}：${r.error}` });
    } catch (e: any) { setMsg({ ok: false, text: e.message }); }
    finally { setTesting(null); }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorBox msg={error} onRetry={reload} />;
  return (
    <>
      <h1>资讯源管理</h1>
      <Card title="添加资讯源">
        {msg && <Msg ok={msg.ok} text={msg.text} />}
        <div className="row">
          <label className="field">名称<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label className="field" style={{ flex: 2 }}>RSS/Atom 地址<input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://..." /></label>
          <label className="field">类型<select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}><option>rss</option><option>atom</option></select></label>
          <label className="field">语言<select value={form.lang} onChange={(e) => setForm({ ...form, lang: e.target.value })}><option>en</option><option>zh</option></select></label>
        </div>
        <button className="btn btn-primary" onClick={create}>添加</button>
      </Card>
      <Card title={`来源列表（${data?.items.length ?? 0}）`}>
        {!data?.items.length ? <Empty /> : (
          <table>
            <thead><tr><th>名称</th><th>地址</th><th>类型</th><th>状态</th><th>备注</th><th>操作</th></tr></thead>
            <tbody>
              {data!.items.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td className="muted" style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.url}</td>
                  <td>{s.type} / {s.lang}</td>
                  <td>{s.enabled ? <span className="badge" style={{ background: "#059669" }}>启用</span> : <span className="badge" style={{ background: "#94a3b8" }}>禁用</span>}</td>
                  <td className="muted">{s.note || ""}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="btn btn-sm" onClick={() => toggle(s)}>{s.enabled ? "禁用" : "启用"}</button>{" "}
                    <button className="btn btn-sm" disabled={testing === s.id} onClick={() => test(s)}>{testing === s.id ? "测试中" : "连通测试"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
