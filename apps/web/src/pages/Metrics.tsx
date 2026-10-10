import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Card, Empty, ErrorBox, Loading, Msg, Stat, useFetch } from "../components";

type Article = { id: number; title: string; status: string };
type MetricRow = {
  stat_date: string; reads: number | null; likes: number | null; comments: number | null;
  shares: number | null; revenue: number | null; note: string | null;
};
type Overview = { reads_total: number; engagements_total: number; revenue_total: number };

const todayStr = () => new Date().toISOString().slice(0, 10);

export default function Metrics() {
  const overview = useFetch<Overview>("/api/v1/dashboard/overview");
  const articles = useFetch<{ count: number; items: Article[] }>("/api/v1/articles?limit=200");
  const [articleId, setArticleId] = useState<number | "">("");
  const metrics = useFetch<{ count: number; items: MetricRow[] }>(
    articleId === "" ? null : `/api/v1/articles/${articleId}/metrics`
  );
  const [mform, setMform] = useState({ stat_date: todayStr(), reads: "", likes: "", comments: "", shares: "", revenue: "" });
  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (articles.data && articleId === "" && articles.data.items.length > 0) {
      setArticleId(articles.data.items[0].id);
    }
  }, [articles.data, articleId]);

  async function save() {
    if (articleId === "") return;
    setBusy(true);
    setAct(null);
    try {
      await api.post(`/api/v1/articles/${articleId}/metrics`, {
        stat_date: mform.stat_date,
        reads: mform.reads === "" ? null : Number(mform.reads),
        likes: mform.likes === "" ? null : Number(mform.likes),
        comments: mform.comments === "" ? null : Number(mform.comments),
        shares: mform.shares === "" ? null : Number(mform.shares),
        revenue: mform.revenue === "" ? null : Number(mform.revenue),
      });
      setAct({ ok: true, text: `${mform.stat_date} 数据已保存` });
      void metrics.reload();
      void overview.reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>阅读与收益</h1>
      {act && <Msg ok={act.ok} text={act.text} />}
      {overview.data && (
        <div className="stats">
          <Stat label="累计阅读" value={overview.data.reads_total} />
          <Stat label="累计互动" value={overview.data.engagements_total} />
          <Stat label="累计收益" value={`¥${overview.data.revenue_total}`} tone="good" />
        </div>
      )}
      <Card title="录入单篇文章数据">
        <div className="row">
          <label className="field" style={{ flex: "1 1 260px" }}>
            文章
            <select value={articleId} onChange={(e) => setArticleId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">选择文章</option>
              {articles.data?.items.map((a) => (
                <option key={a.id} value={a.id}>#{a.id} {a.title.slice(0, 36)}（{a.status}）</option>
              ))}
            </select>
          </label>
          <label className="field" style={{ flex: "0 0 150px" }}>统计日期
            <input type="date" value={mform.stat_date} onChange={(e) => setMform({ ...mform, stat_date: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "0 0 110px" }}>阅读量
            <input type="number" value={mform.reads} onChange={(e) => setMform({ ...mform, reads: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "0 0 110px" }}>点赞
            <input type="number" value={mform.likes} onChange={(e) => setMform({ ...mform, likes: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "0 0 110px" }}>评论
            <input type="number" value={mform.comments} onChange={(e) => setMform({ ...mform, comments: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "0 0 110px" }}>分享
            <input type="number" value={mform.shares} onChange={(e) => setMform({ ...mform, shares: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "0 0 130px" }}>收益（元）
            <input type="number" step="0.01" value={mform.revenue} onChange={(e) => setMform({ ...mform, revenue: e.target.value })} />
          </label>
          <div style={{ alignSelf: "flex-end" }}>
            <button className="btn btn-primary" disabled={busy || articleId === ""} onClick={save}>保存</button>
          </div>
        </div>
      </Card>
      {articleId !== "" && (
        <Card title="该文章历史数据">
          {!metrics.data ? (metrics.loading ? <Loading /> : metrics.error ? <ErrorBox msg={metrics.error} onRetry={metrics.reload} /> : <Empty />) :
            metrics.data.items.length ? (
              <table>
                <thead><tr><th>日期</th><th>阅读</th><th>点赞</th><th>评论</th><th>分享</th><th>收益（元）</th><th>备注</th></tr></thead>
                <tbody>
                  {metrics.data.items.map((m) => (
                    <tr key={m.stat_date}>
                      <td>{m.stat_date}</td>
                      <td>{m.reads ?? "-"}</td>
                      <td>{m.likes ?? "-"}</td>
                      <td>{m.comments ?? "-"}</td>
                      <td>{m.shares ?? "-"}</td>
                      <td>{m.revenue ?? "-"}</td>
                      <td className="muted">{m.note || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Empty msg="还没有数据，发布后按头条后台实际数字录入" />}
        </Card>
      )}
      <Card title="提示">
        <div className="muted">
          数据必须依据头条后台真实结果录入；也可以逐篇在<Link to={`/articles/${typeof articleId === "number" ? articleId : 1}`}>文章详情页</Link>底部录入。
        </div>
      </Card>
    </>
  );
}
