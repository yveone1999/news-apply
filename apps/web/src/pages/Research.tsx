import { useState } from "react";
import { api } from "../api";
import { Badge, Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type Topic = { id: number; title: string; score: number; status: string; column_name: string | null };
type ResearchSummary = { id: number; topic_id: number; conclusion: string | null; evidence_count: number; created_at: string };
type Evidence = { fact: string; source_title: string; source_url: string; verified: boolean };
type ResearchDetail = {
  id: number; topic_id: number; content: string; evidence: Evidence[];
  open_questions: string[]; conclusion: string | null; created_at: string;
};

export default function Research() {
  const topics = useFetch<{ count: number; items: Topic[] }>("/api/v1/topics?limit=100");
  const [topicId, setTopicId] = useState<number | "">("");
  const [researchId, setResearchId] = useState<number | null>(null);
  const summaries = useFetch<{ count: number; items: ResearchSummary[] }>(
    topicId === "" ? null : `/api/v1/research?topic_id=${topicId}`
  );
  const detail = useFetch<ResearchDetail>(researchId === null ? null : `/api/v1/research/${researchId}`);
  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function runResearch() {
    if (topicId === "") return;
    setBusy(true);
    setAct({ ok: true, text: "研究运行中（约 1-2 分钟）…" });
    try {
      const r = await api.post<{ verified_count: number }>(`/api/v1/topics/${topicId}/research`);
      setAct({ ok: true, text: `研究完成：已核验证据 ${r.verified_count} 条` });
      setResearchId(null);
      void summaries.reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>研究与事实核验</h1>
      {act && <Msg ok={act.ok} text={act.text} />}
      <Card title="选择选题">
        <div className="row">
          <label className="field" style={{ flex: "1 1 320px" }}>
            选题
            <select
              value={topicId}
              onChange={(e) => { setTopicId(e.target.value ? Number(e.target.value) : ""); setResearchId(null); }}
            >
              <option value="">请选择选题</option>
              {topics.data?.items.map((t) => (
                <option key={t.id} value={t.id}>#{t.id} {t.title}（{t.score} 分）</option>
              ))}
            </select>
          </label>
          <div style={{ alignSelf: "flex-end" }}>
            <button className="btn btn-primary" disabled={topicId === "" || busy} onClick={runResearch}>
              {busy ? "研究中…" : "运行研究"}
            </button>
          </div>
        </div>
        {topicId !== "" && (
          summaries.loading ? <Loading /> :
          summaries.error ? <ErrorBox msg={summaries.error} onRetry={summaries.reload} /> :
          summaries.data?.items.length ? (
            <table style={{ marginTop: 12 }}>
              <thead><tr><th>档案</th><th>证据数</th><th>结论摘要</th><th>创建时间</th><th></th></tr></thead>
              <tbody>
                {summaries.data!.items.map((s) => (
                  <tr key={s.id}>
                    <td>#{s.id}</td>
                    <td>{s.evidence_count}</td>
                    <td>{(s.conclusion || "").slice(0, 60)}</td>
                    <td className="muted">{s.created_at}</td>
                    <td><button className="btn btn-sm" onClick={() => setResearchId(s.id)}>查看</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg="该选题还没有研究档案，点击「运行研究」" />
        )}
      </Card>

      {researchId !== null && (
        detail.loading ? <Loading /> :
        detail.error ? <ErrorBox msg={detail.error} onRetry={detail.reload} /> :
        detail.data && (
          <>
            <Card title={`研究档案 #${detail.data.id} · 选题 #${detail.data.topic_id}`}>
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{detail.data.content}</div>
            </Card>
            <Card title={`事实证据（${detail.data.evidence.length} 条）`}>
              {detail.data.evidence.length ? (
                <table>
                  <thead><tr><th>事实</th><th>来源</th><th>链接</th><th>核验</th></tr></thead>
                  <tbody>
                    {detail.data.evidence.map((ev, i) => (
                      <tr key={i}>
                        <td>{ev.fact}</td>
                        <td>{ev.source_title || "-"}</td>
                        <td>
                          {ev.source_url
                            ? <a href={ev.source_url} target="_blank" rel="noreferrer">打开来源</a>
                            : <span className="muted">无链接（不可核验已清空）</span>}
                        </td>
                        <td>{ev.verified ? <Badge value="done" /> : <Badge value="failed" />}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <Empty msg="研究档案中没有任何证据（质量门禁会硬阻断）" />}
            </Card>
            {detail.data.open_questions.length > 0 && (
              <Card title="待核验问题">
                {detail.data.open_questions.map((q, i) => <div className="issue issue-warn" key={i}>{q}</div>)}
              </Card>
            )}
            {detail.data.conclusion && (
              <Card title="研究结论"><div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{detail.data.conclusion}</div></Card>
            )}
          </>
        )
      )}
    </>
  );
}
