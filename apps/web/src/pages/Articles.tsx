import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, Empty, ErrorBox, Loading, useFetch } from "../components";

type Article = {
  id: number; topic_id: number; title: string; column_name: string | null;
  status: string; current_version: number; quality_passed: boolean | null; updated_at: string;
};

const STATUS_OPTIONS: [string, string][] = [
  ["", "全部"], ["draft", "草稿"], ["in_review", "审核中"], ["approved", "已批准"],
  ["rejected", "已退回"], ["published", "已发布"],
];

export default function Articles() {
  const [status, setStatus] = useState("");
  const { data, loading, error, reload } = useFetch<{ count: number; items: Article[] }>(
    `/api/v1/articles?limit=100${status ? `&status=${status}` : ""}`, [status]
  );

  return (
    <>
      <h1>文章管理</h1>
      <Card>
        <div className="row" style={{ marginBottom: 12 }}>
          <label className="field" style={{ flex: "0 0 160px" }}>
            状态
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_OPTIONS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
            </select>
          </label>
        </div>
        {!data ? (loading ? <Loading /> : error ? <ErrorBox msg={error} onRetry={reload} /> : <Empty />) : (
          data.items.length ? (
            <table>
              <thead>
                <tr><th>ID</th><th>标题</th><th>栏目</th><th>版本</th><th>门禁</th><th>状态</th><th>更新时间</th></tr>
              </thead>
              <tbody>
                {data.items.map((a) => (
                  <tr key={a.id}>
                    <td>{a.id}</td>
                    <td><Link to={`/articles/${a.id}`}>{a.title}</Link></td>
                    <td>{a.column_name || "-"}</td>
                    <td>v{a.current_version}</td>
                    <td>
                      {a.quality_passed === null
                        ? <span className="muted">未运行</span>
                        : a.quality_passed
                          ? <span style={{ color: "#059669" }}>通过</span>
                          : <span style={{ color: "#dc2626" }}>未通过</span>}
                    </td>
                    <td><Badge value={a.status} /></td>
                    <td className="muted">{a.updated_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg="还没有文章：先采集资讯 → 生成选题 → 研究 → 生成文章" />
        )}
      </Card>
    </>
  );
}
