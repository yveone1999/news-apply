import { useState } from "react";
import { api } from "../api";
import { Badge, Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type Run = {
  id: number; run_type: string; status: string; error: string | null;
  started_at: string; finished_at: string | null;
};

const TYPE_OPTIONS: [string, string][] = [
  ["", "全部"], ["collect", "采集"], ["topics", "选题"], ["research", "研究"],
  ["write_article", "写作"], ["quality_check", "质量门禁"],
];

export default function Tasks() {
  const [type, setType] = useState("");
  const { data, loading, error, reload } = useFetch<{ count: number; items: Run[] }>(
    `/api/v1/workflow-runs?limit=100${type ? `&run_type=${type}` : ""}`, [type]
  );
  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState("");

  async function quickRun(kind: "collect" | "topics") {
    setBusy(kind);
    setAct({ ok: true, text: kind === "collect" ? "采集运行中…" : "选题生成中（约 1-2 分钟）…" });
    try {
      if (kind === "collect") {
        const r = await api.post<{ sources_ok: number; sources_total: number; items_added: number }>("/api/v1/collect/run");
        setAct({ ok: true, text: `采集完成：${r.sources_ok}/${r.sources_total} 源正常，新增 ${r.items_added} 条` });
      } else {
        const r = await api.post<{ created: number }>("/api/v1/topics/generate", { max_topics: 5, hours: 24 });
        setAct({ ok: true, text: `选题完成：新增 ${r.created} 个选题` });
      }
      void reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <h1>任务中心</h1>
      {act && <Msg ok={act.ok} text={act.text} />}
      <Card title="手动触发">
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-primary" disabled={busy !== ""} onClick={() => quickRun("collect")}>
            {busy === "collect" ? "采集中…" : "运行采集"}
          </button>
          <button className="btn btn-primary" disabled={busy !== ""} onClick={() => quickRun("topics")}>
            {busy === "topics" ? "生成中…" : "生成今日选题"}
          </button>
        </div>
        <div className="muted" style={{ marginTop: 8 }}>同一天的重复触发会幂等返回历史记录，不会重复生成。</div>
      </Card>
      <Card title="执行历史">
        <div className="row" style={{ marginBottom: 12 }}>
          <label className="field" style={{ flex: "0 0 160px" }}>
            类型
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {TYPE_OPTIONS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
            </select>
          </label>
        </div>
        {!data ? (loading ? <Loading /> : error ? <ErrorBox msg={error} onRetry={reload} /> : <Empty />) :
          data.items.length ? (
            <table>
              <thead><tr><th>ID</th><th>类型</th><th>状态</th><th>开始时间</th><th>结束时间</th><th>错误</th></tr></thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td>{r.run_type}</td>
                    <td><Badge value={r.status} /></td>
                    <td className="muted">{r.started_at}</td>
                    <td className="muted">{r.finished_at || "-"}</td>
                    <td title={r.error || undefined} style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.error || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg="还没有任务记录" />}
      </Card>
    </>
  );
}
