import { Link } from "react-router-dom";
import { Badge, Card, Empty, ErrorBox, Loading, useFetch } from "../components";

type Pub = {
  id: number; article_id: number; title: string; platform: string; url: string;
  status: string; published_at: string; note: string | null;
};

export default function Publishing() {
  const { data, loading, error, reload } = useFetch<{ count: number; items: Pub[] }>("/api/v1/publishing");

  return (
    <>
      <h1>发布记录</h1>
      <Card>
        <div className="muted" style={{ marginBottom: 10 }}>
          这里只记录人工在今日头条完成发布后的回填信息；「审核通过」不等于「已发布」。
        </div>
        {!data ? (loading ? <Loading /> : error ? <ErrorBox msg={error} onRetry={reload} /> : <Empty msg="还没有发布记录" />) :
          data.items.length ? (
            <table>
              <thead><tr><th>文章</th><th>平台</th><th>链接</th><th>状态</th><th>发布时间</th><th>备注</th></tr></thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id}>
                    <td><Link to={`/articles/${p.article_id}`}>{p.title}</Link></td>
                    <td>{p.platform}</td>
                    <td><a href={p.url} target="_blank" rel="noreferrer">打开</a></td>
                    <td><Badge value={p.status} /></td>
                    <td className="muted">{p.published_at}</td>
                    <td className="muted">{p.note || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg="还没有发布记录" />}
      </Card>
    </>
  );
}
