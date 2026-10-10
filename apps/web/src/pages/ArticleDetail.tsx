import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Badge, Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type Version = { version: number; title: string; change_note: string | null; created_at: string };
type FactCheck = {
  facts: unknown[]; unsupported: string[]; unmarked_uncertainty: string[];
  logic: string[]; comment: string;
};
type QualityReport = { passed: boolean; issues: string[]; fact_check: FactCheck; evidence_count: number };
type Article = {
  id: number; topic_id: number; title: string; summary: string | null; column_name: string | null;
  status: string; body: string; current_version: number;
  quality_report: QualityReport | null; versions: Version[];
};
type MetricRow = {
  stat_date: string; reads: number | null; likes: number | null; comments: number | null;
  shares: number | null; revenue: number | null; note: string | null;
};

const todayStr = () => new Date().toISOString().slice(0, 10);

export default function ArticleDetail() {
  const { id } = useParams();
  const articleId = Number(id);
  const { data: article, loading, error, reload } = useFetch<Article>(
    articleId ? `/api/v1/articles/${articleId}` : null
  );
  const metrics = useFetch<{ count: number; items: MetricRow[] }>(
    articleId ? `/api/v1/articles/${articleId}/metrics` : null
  );

  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState("");
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ title: "", summary: "", body: "", change_note: "" });
  const [review, setReview] = useState({ reviewer: "human", note: "" });
  const [rejectIssues, setRejectIssues] = useState("");
  const [publish, setPublish] = useState({ url: "", platform: "toutiao", note: "" });
  const [mform, setMform] = useState({
    stat_date: todayStr(), reads: "", likes: "", comments: "", shares: "", revenue: "",
  });

  useEffect(() => {
    if (article) {
      setForm({ title: article.title, summary: article.summary || "", body: article.body, change_note: "" });
    }
  }, [article?.id, article?.current_version]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!articleId) return <Empty msg="缺少文章 ID" />;
  if (loading) return <Loading />;
  if (error) return <ErrorBox msg={error} onRetry={reload} />;
  if (!article) return <Empty msg="文章不存在" />;

  const canEdit = article.status === "draft" || article.status === "rejected";
  const report = article.quality_report;

  async function run(op: string, fn: () => Promise<unknown>, okText: string) {
    setBusy(op);
    setAct(null);
    try {
      await fn();
      setAct({ ok: true, text: okText });
      void reload();
      void metrics.reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    } finally {
      setBusy("");
    }
  }

  const saveEdit = () =>
    run("edit", () => api.put(`/api/v1/articles/${articleId}`, {
      title: form.title, summary: form.summary, body: form.body,
      change_note: form.change_note || undefined,
    }), "已保存，生成新版本（质量报告已失效，需重新运行门禁）").then(() => setEditing(false));

  const revise = () =>
    run("revise", () => api.post("/api/v1/articles/generate", {
      topic_id: article!.topic_id,
      issues: article!.quality_report!.issues,
      change_note: "修正版：处理门禁问题",
    }), "修正版已生成，请重新运行质量门禁");

  const qualityCheck = () =>
    run("qc", () => api.post(`/api/v1/articles/${articleId}/quality-check`), "质量门禁完成，结果见下方报告（约 1-2 分钟）");

  const submit = () => run("submit", () => api.post(`/api/v1/articles/${articleId}/submit`), "已提交人工审核");
  const approve = () => run("approve", () => api.post(`/api/v1/articles/${articleId}/approve`, {
    reviewer: review.reviewer, note: review.note || undefined,
  }), "已批准：现在可以记录发布");
  const reject = () => run("reject", () => api.post(`/api/v1/articles/${articleId}/reject`, {
    reviewer: review.reviewer, note: review.note || undefined,
    issues: rejectIssues.split("\n").map((s) => s.trim()).filter(Boolean),
  }), "已退回修改");
  const reedit = () => run("reedit", () => api.post(`/api/v1/articles/${articleId}/reedit`), "已回到草稿状态，可编辑");
  const recordPublish = () => run("publish", () => api.post(`/api/v1/articles/${articleId}/publish`, {
    url: publish.url, platform: publish.platform, note: publish.note || undefined,
  }), "已记录发布，状态更新为已发布");
  const restore = (v: number) =>
    run("restore", () => api.post(`/api/v1/articles/${articleId}/versions/${v}/restore`), `已恢复自 v${v}`);

  const saveMetrics = () =>
    run("metrics", () => api.post(`/api/v1/articles/${articleId}/metrics`, {
      stat_date: mform.stat_date,
      reads: mform.reads === "" ? null : Number(mform.reads),
      likes: mform.likes === "" ? null : Number(mform.likes),
      comments: mform.comments === "" ? null : Number(mform.comments),
      shares: mform.shares === "" ? null : Number(mform.shares),
      revenue: mform.revenue === "" ? null : Number(mform.revenue),
    }), `${mform.stat_date} 数据已保存`);

  return (
    <>
      <div style={{ marginBottom: 8 }}><Link to="/articles">← 返回文章列表</Link></div>
      <h1>{article.title}</h1>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <Badge value={article.status} />
        <span className="muted">栏目：{article.column_name || "-"}</span>
        <span className="muted">当前版本：v{article.current_version}</span>
        <span className="muted">选题 #{article.topic_id}</span>
      </div>
      {act && <Msg ok={act.ok} text={act.text} />}

      <Card title="正文" actions={canEdit && !editing ? <button className="btn" onClick={() => setEditing(true)}>编辑</button> : undefined}>
        {editing ? (
          <>
            <label className="field">标题
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>
            <label className="field">摘要
              <textarea style={{ minHeight: 60 }} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
            </label>
            <label className="field">正文
              <textarea style={{ minHeight: 320 }} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
            </label>
            <label className="field">修改说明
              <input value={form.change_note} onChange={(e) => setForm({ ...form, change_note: e.target.value })} placeholder="例如：修正第三段数字" />
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" disabled={busy === "edit"} onClick={saveEdit}>
                {busy === "edit" ? "保存中…" : "保存新版本"}
              </button>
              <button className="btn" onClick={() => setEditing(false)}>取消</button>
            </div>
          </>
        ) : (
          <>
            {article.summary && <p className="muted" style={{ marginBottom: 8 }}>{article.summary}</p>}
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.8 }}>{article.body}</div>
            <div className="muted" style={{ marginTop: 8 }}>{article.body.length} 字</div>
          </>
        )}
      </Card>

      {report && (
        <Card title="质量门禁报告">
          <div style={{ marginBottom: 8 }}>
            {report.passed ? <Badge value="done" /> : <Badge value="failed" />}
            <span className="muted" style={{ marginLeft: 8 }}>研究证据 {report.evidence_count} 条</span>
          </div>
          {report.issues.length ? (
            <>
              <h2>问题清单（{report.issues.length}）</h2>
              {report.issues.map((iss, i) => <div className="issue" key={i}>{iss}</div>)}
            </>
          ) : <div className="msg ok">没有发现问题，可以提交人工审核</div>}
          <h2>事实核查明细</h2>
          <div className="muted">
            无依据陈述：{report.fact_check.unsupported.length} · 未标注不确定性：
            {report.fact_check.unmarked_uncertainty.length} · 逻辑问题：{report.fact_check.logic.length}
          </div>
          {report.fact_check.comment && <div className="muted" style={{ marginTop: 4 }}>核查员：{report.fact_check.comment}</div>}
        </Card>
      )}

      <Card title="操作">
        {canEdit && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn btn-primary" disabled={busy !== ""} onClick={qualityCheck}>
              {busy === "qc" ? "门禁运行中…" : "运行质量门禁"}
            </button>
            {report?.passed && (
              <button className="btn btn-primary" disabled={busy !== ""} onClick={submit}>提交人工审核</button>
            )}
            {report && !report.passed && (
              <button className="btn" disabled={busy !== ""} onClick={revise}>
                {busy === "revise" ? "生成修正版中…" : "生成修正版（把门禁问题传给模型重写）"}
              </button>
            )}
            {!report && <span className="muted">先运行质量门禁，通过后才能提交审核</span>}
          </div>
        )}
        {article.status === "in_review" && (
          <>
            <h2>人工审批</h2>
            <div className="row">
              <label className="field" style={{ flex: "0 0 160px" }}>审核人
                <input value={review.reviewer} onChange={(e) => setReview({ ...review, reviewer: e.target.value })} />
              </label>
              <label className="field">审批意见
                <input value={review.note} onChange={(e) => setReview({ ...review, note: e.target.value })} placeholder="可选" />
              </label>
            </div>
            <label className="field">退回问题清单（仅退回时填写，每行一条）
              <textarea style={{ minHeight: 60 }} value={rejectIssues} onChange={(e) => setRejectIssues(e.target.value)} />
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" disabled={busy !== ""} onClick={approve}>批准</button>
              <button className="btn btn-danger" disabled={busy !== ""} onClick={reject}>退回修改</button>
            </div>
          </>
        )}
        {article.status === "rejected" && (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="btn" disabled={busy !== ""} onClick={reedit}>回到草稿重新编辑</button>
            <span className="muted">或直接用上方「编辑」/「生成修正版」处理</span>
          </div>
        )}
        {article.status === "approved" && (
          <>
            <h2>记录发布（人工在今日头条发布后回填）</h2>
            <div className="row">
              <label className="field" style={{ flex: "0 0 140px" }}>平台
                <input value={publish.platform} onChange={(e) => setPublish({ ...publish, platform: e.target.value })} />
              </label>
              <label className="field">文章链接
                <input value={publish.url} onChange={(e) => setPublish({ ...publish, url: e.target.value })} placeholder="https://www.toutiao.com/article/..." />
              </label>
              <label className="field" style={{ flex: "0 0 180px" }}>备注
                <input value={publish.note} onChange={(e) => setPublish({ ...publish, note: e.target.value })} placeholder="可选" />
              </label>
            </div>
            <button className="btn btn-primary" disabled={busy !== "" || publish.url.trim().length < 5} onClick={recordPublish}>
              记录已发布
            </button>
          </>
        )}
        {article.status === "published" && (
          <div className="msg ok">已发布。查看发布记录：<Link to="/publishing">发布记录页</Link></div>
        )}
      </Card>

      <Card title={`版本历史（${article.versions.length}）`}>
        <table>
          <thead><tr><th>版本</th><th>标题</th><th>变更说明</th><th>时间</th><th></th></tr></thead>
          <tbody>
            {article.versions.map((v) => (
              <tr key={v.version}>
                <td>v{v.version}</td>
                <td>{v.title}</td>
                <td className="muted">{v.change_note || "-"}</td>
                <td className="muted">{v.created_at}</td>
                <td>
                  {canEdit && v.version !== article.current_version && (
                    <button className="btn btn-sm" disabled={busy !== ""} onClick={() => restore(v.version)}>恢复</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="阅读与收益数据">
        <div className="row">
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
            <button className="btn btn-primary" disabled={busy === "metrics"} onClick={saveMetrics}>保存</button>
          </div>
        </div>
        <div className="muted" style={{ margin: "8px 0" }}>同一日期重复保存会覆盖（按头条后台当天实际数据填写）。</div>
        {metrics.data && metrics.data.items.length > 0 && (
          <table>
            <thead><tr><th>日期</th><th>阅读</th><th>点赞</th><th>评论</th><th>分享</th><th>收益（元）</th></tr></thead>
            <tbody>
              {metrics.data.items.map((m) => (
                <tr key={m.stat_date}>
                  <td>{m.stat_date}</td>
                  <td>{m.reads ?? "-"}</td>
                  <td>{m.likes ?? "-"}</td>
                  <td>{m.comments ?? "-"}</td>
                  <td>{m.shares ?? "-"}</td>
                  <td>{m.revenue ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
