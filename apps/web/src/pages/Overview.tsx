import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Badge, Card, Empty, ErrorBox, Loading, Msg, Stat, useFetch } from "../components";

type Overview = {
  pending_review: number; drafts: number; published_total: number; news_last_24h: number;
  topics_candidate: number; reads_total: number; engagements_total: number; revenue_total: number;
  runs_today: number; failed_runs_today: number; failed_runs: { id: string; run_type: string; error: string }[];
};

export default function Overview() {
  const { data, loading, error, reload } = useFetch<Overview>("/api/v1/dashboard/overview");
  const articles = useFetch<{ items: { id: number; title: string; status: string; column_name: string | null }[] }>(
    "/api/v1/articles?limit=20"
  );
  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);

  async function run(kind: "collect" | "topics") {
    setAct({ ok: true, text: kind === "collect" ? "采集运行中…" : "选题生成中（约 1-2 分钟）…" });
    try {
      if (kind === "collect") {
        const r = await api.post<{ sources_ok: number; sources_total: number; items_added: number }>("/api/v1/collect/run");
        setAct({ ok: true, text: `采集完成：${r.sources_ok}/${r.sources_total} 源，新增 ${r.items_added} 条` });
      } else {
        const r = await api.post<{ created: number }>("/api/v1/topics/generate", { max_topics: 5, hours: 24 });
        setAct({ ok: true, text: `选题完成：新增 ${r.created} 个选题` });
      }
      void reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorBox msg={error} onRetry={reload} />;
  if (!data) return <Empty />;

  return (
    <>
      <h1>运营总览</h1>
      {act && <Msg ok={act.ok} text={act.text} />}
      <div className="stats">
        <Stat label="待审稿件" value={data.pending_review} tone={data.pending_review > 0 ? "bad" : undefined} />
        <Stat label="草稿" value={data.drafts} />
        <Stat label="已发布" value={data.published_total} tone="good" />
        <Stat label="近24h资讯" value={data.news_last_24h} />
        <Stat label="候选选题" value={data.topics_candidate} />
        <Stat label="累计阅读" value={data.reads_total} />
        <Stat label="累计互动" value={data.engagements_total} />
        <Stat label="累计收益" value={`¥${data.revenue_total}`} tone="good" />
        <Stat label="今日任务" value={data.runs_today} />
        <Stat label="今日失败" value={data.failed_runs_today} tone={data.failed_runs_today > 0 ? "bad" : undefined} />
      </div>
      <div className="row">
        <div style={{ flex: 1 }}>
          <Card title="快速操作">
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" onClick={() => run("collect")}>运行采集</button>
              <button className="btn btn-primary" onClick={() => run("topics")}>生成今日选题</button>
            </div>
            <div className="muted" style={{ marginTop: 8 }}>当日重复触发会自动幂等返回，不会重复生成</div>
          </Card>
        </div>
        <div style={{ flex: 1 }}>
          <Card title="最近文章" actions={<Link className="btn btn-sm" to="/articles">全部</Link>}>
            {articles.loading ? <Loading /> : articles.error ? <ErrorBox msg={articles.error} /> : articles.data?.items.length ? (
              <table>
                <tbody>
                  {articles.data!.items.slice(0, 8).map((a) => (
                    <tr key={a.id}>
                      <td><Link to={`/articles/${a.id}`}>{a.title.slice(0, 30)}</Link></td>
                      <td><Badge value={a.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Empty msg="还没有文章，先采集资讯并生成选题" />}
          </Card>
        </div>
      </div>
      {data.failed_runs.length > 0 && (
        <Card title="今日失败任务">
          {data.failed_runs.map((r) => (
            <div className="issue" key={r.id}>[{r.run_type}] {r.error}</div>
          ))}
        </Card>
      )}
    </>
  );
}
