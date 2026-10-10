import { Link } from "react-router-dom";
import { Card, Empty, ErrorBox, Loading, useFetch } from "../components";

type Article = {
  id: number; title: string; column_name: string | null;
  current_version: number; quality_passed: boolean | null; updated_at: string;
};

export default function Review() {
  const { data, loading, error, reload } = useFetch<{ count: number; items: Article[] }>(
    "/api/v1/articles?status=in_review&limit=100"
  );

  return (
    <>
      <h1>审核队列</h1>
      <Card title="待人工审批的稿件（质量门禁已通过）">
        <div className="muted" style={{ marginBottom: 10 }}>
          审批操作（批准 / 退回修改）在文章详情页进行。只有人工批准后才能记录发布。
        </div>
        {!data ? (loading ? <Loading /> : error ? <ErrorBox msg={error} onRetry={reload} /> : <Empty msg="当前没有待审稿件" />) :
          data.items.length ? (
            <table>
              <thead><tr><th>ID</th><th>标题</th><th>栏目</th><th>版本</th><th>门禁</th><th>提交时间</th><th></th></tr></thead>
              <tbody>
                {data.items.map((a) => (
                  <tr key={a.id}>
                    <td>{a.id}</td>
                    <td>{a.title}</td>
                    <td>{a.column_name || "-"}</td>
                    <td>v{a.current_version}</td>
                    <td>{a.quality_passed ? <span style={{ color: "#059669" }}>通过</span> : <span style={{ color: "#dc2626" }}>未通过</span>}</td>
                    <td className="muted">{a.updated_at}</td>
                    <td><Link className="btn btn-sm" to={`/articles/${a.id}`}>去审批</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg="当前没有待审稿件" />}
      </Card>
    </>
  );
}
