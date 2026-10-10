import { useMemo, useState } from "react";
import { api } from "../api";
import { Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type Item = { id: number; source_id: number; title: string; link: string | null; published_at: string | null; summary: string; created_at: string };

export default function News() {
  const { data, loading, error, reload } = useFetch<{ items: Item[] }>("/api/v1/news-items?limit=200");
  const sources = useFetch<{ items: { id: number; name: string }[] }>("/api/v1/news-sources");
  const [q, setQ] = useState("");
  const [sourceId, setSourceId] = useState<number | "">("");
  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);

  const filtered = useMemo(() => {
    let items = data?.items ?? [];
    if (sourceId !== "") items = items.filter((i) => i.source_id === Number(sourceId));
    if (q) items = items.filter((i) => i.title.toLowerCase().includes(q.toLowerCase()) || (i.summary || "").toLowerCase().includes(q.toLowerCase()));
    return items;
  }, [data, q, sourceId]);

  async function collect() {
    setAct({ ok: true, text: "采集运行中（约 30-60 秒）…" });
    try {
      const r = await api.post<{ sources_ok: number; sources_total: number; items_added: number; note?: string }>("/api/v1/collect/run");
      setAct({ ok: true, text: r.note ? r.note : `完成：${r.sources_ok}/${r.sources_total} 源，新增 ${r.items_added} 条` });
      void reload();
    } catch (e: any) { setAct({ ok: false, text: e.message }); }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorBox msg={error} onRetry={reload} />;
  return (
    <>
      <h1>资讯列表与去重</h1>
      {act && <Msg ok={act.ok} text={act.text} />}
      <Card title={`已采集资讯（显示 ${filtered.length} 条，按内容哈希去重，重复自动跳过）`}
        actions={<button className="btn btn-primary" onClick={collect}>运行采集</button>}>
        <div className="row" style={{ marginBottom: 12 }}>
          <label className="field">关键词<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="标题/摘要搜索" /></label>
          <label className="field">来源
            <select value={sourceId} onChange={(e) => setSourceId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">全部</option>
              {sources.data?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        </div>
        {!filtered.length ? <Empty msg="没有匹配的资讯，先运行采集" /> : (
          <table>
            <thead><tr><th>标题</th><th>来源</th><th>发布时间</th><th>摘要</th></tr></thead>
            <tbody>
              {filtered.map((i) => (
                <tr key={i.id}>
                  <td style={{ maxWidth: 380 }}>{i.link ? <a href={i.link} target="_blank" rel="noreferrer">{i.title}</a> : i.title}</td>
                  <td className="muted">{sources.data?.items.find((s) => s.id === i.source_id)?.name || `#${i.source_id}`}</td>
                  <td className="muted" style={{ whiteSpace: "nowrap" }}>{(i.published_at || "").slice(0, 16)}</td>
                  <td className="muted" style={{ maxWidth: 320 }}>{(i.summary || "").slice(0, 80)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
