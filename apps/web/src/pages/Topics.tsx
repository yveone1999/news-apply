import { useState } from "react";
import { api } from "../api";
import { Badge, Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type Topic = { id: number; title: string; column_name: string; score: number | null; status: string; item_ids: number[]; created_at: string };

export default function Topics() {
  const { data, loading, error, reload } = useFetch<{ items: Topic[] }>("/api/v1/topics?limit=100");
  const [form, setForm] = useState({ max_topics: 5, hours: 24 });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function generate() {
    setMsg({ ok: true, text: "LLM 选题评分中（约 1-2 分钟）…" });
    try {
      const r = await api.post<{ created: number; topics: { title: string; score: number }[] }>("/api/v1/topics/generate", form);
      setMsg({ ok: true, text: `完成：新增 ${r.created} 个选题（同题自动去重）` });
      void reload();
    } catch (e: any) { setMsg({ ok: false, text: e.message }); }
  }
  async function research(t: Topic) {
    setBusy(`r${t.id}`);
    setMsg(null);
    try {
      const r = await api.post<{ research_id: number; verified_count: number; evidence: unknown[] }>(`/api/v1/topics/${t.id}/research`);
      setMsg({ ok: true, text: `研究完成：${r.verified_count}/${r.evidence.length} 条证据已证实，可在「研究与核验」查看` });
      void reload();
    } catch (e: any) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(null); }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorBox msg={error} onRetry={reload} />;
  return (
    <>
      <h1>选题池（100 分制）</h1>
      {msg && <Msg ok={msg.ok} text={msg.text} />}
      <Card title="生成选题（LLM 评分：受众25 / 可靠性25 / 差异化20 / 时效15 / 定位15）">
        <div className="row">
          <label className="field">最多选题数<input type="number" min={1} max={10} value={form.max_topics} onChange={(e) => setForm({ ...form, max_topics: Number(e.target.value) })} /></label>
          <label className="field">时间窗（小时）<input type="number" min={1} max={72} value={form.hours} onChange={(e) => setForm({ ...form, hours: Number(e.target.value) })} /></label>
        </div>
        <button className="btn btn-primary" onClick={generate}>生成选题</button>
      </Card>
      <Card title={`选题列表（${data?.items.length ?? 0}）`}>
        {!data?.items.length ? <Empty msg="还没有选题，点上方按钮生成" /> : (
          <table>
            <thead><tr><th>选题</th><th>分数</th><th>栏目</th><th>状态</th><th>关联资讯</th><th>操作</th></tr></thead>
            <tbody>
              {data!.items.map((t) => (
                <tr key={t.id}>
                  <td style={{ maxWidth: 340 }}>{t.title}</td>
                  <td><b>{t.score ?? "-"}</b></td>
                  <td>{t.column_name}</td>
                  <td><Badge value={t.status} /></td>
                  <td className="muted">{t.item_ids.join(", ")}</td>
                  <td><button className="btn btn-sm" disabled={busy === `r${t.id}`} onClick={() => research(t)}>{busy === `r${t.id}` ? "研究中…" : "运行研究"}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
