import { useState } from "react";
import { Card, Empty, ErrorBox, Loading, useFetch } from "../components";

type ColumnRow = { articles: number; published: number; reads: number; engagements: number; revenue: number };
type TrendPoint = { stat_date: string; reads: number; engagements: number; revenue: number };

export default function Analytics() {
  const columns = useFetch<{ columns: Record<string, ColumnRow> }>("/api/v1/analytics/columns");
  const [days, setDays] = useState(14);
  const trend = useFetch<{ days: number; series: TrendPoint[] }>(`/api/v1/analytics/trend?days=${days}`, [days]);

  const columnEntries = Object.entries(columns.data?.columns ?? {});
  const maxReads = Math.max(1, ...columnEntries.map(([, v]) => v.reads));

  return (
    <>
      <h1>栏目分析</h1>
      <Card title="栏目表现">
        {!columns.data ? (columns.loading ? <Loading /> : columns.error ? <ErrorBox msg={columns.error} onRetry={columns.reload} /> : <Empty />) :
          columnEntries.length ? (
            <table>
              <thead><tr><th>栏目</th><th>文章数</th><th>已发布</th><th>阅读</th><th>互动</th><th>收益（元）</th><th>阅读占比</th></tr></thead>
              <tbody>
                {columnEntries.map(([name, v]) => (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{v.articles}</td>
                    <td>{v.published}</td>
                    <td>{v.reads}</td>
                    <td>{v.engagements}</td>
                    <td>{v.revenue}</td>
                    <td style={{ width: 180 }}>
                      <div className="bar"><div className="bar-fill" style={{ width: `${(v.reads / maxReads) * 100}%` }} /></div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg="还没有文章数据" />}
      </Card>
      <Card title="每日趋势" actions={
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>近 7 天</option>
          <option value={14}>近 14 天</option>
          <option value={30}>近 30 天</option>
        </select>
      }>
        {!trend.data ? (trend.loading ? <Loading /> : trend.error ? <ErrorBox msg={trend.error} onRetry={trend.reload} /> : <Empty />) :
          trend.data.series.length ? (
            <table>
              <thead><tr><th>日期</th><th>阅读</th><th>互动</th><th>收益（元）</th></tr></thead>
              <tbody>
                {trend.data.series.map((p) => (
                  <tr key={p.stat_date}>
                    <td>{p.stat_date}</td>
                    <td>{p.reads}</td>
                    <td>{p.engagements}</td>
                    <td>{p.revenue}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg={`近 ${days} 天没有数据记录`} />}
      </Card>
    </>
  );
}
