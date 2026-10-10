import { ReactNode, useCallback, useEffect, useState } from "react";

export function useFetch<T>(url: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!url);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    if (!url) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData((await resp.json()) as T);
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);
  useEffect(() => { void load(); }, [load]);
  return { data, loading, error, reload: load };
}

const STATUS_COLORS: Record<string, string> = {
  draft: "#64748b", in_review: "#d97706", approved: "#059669", rejected: "#dc2626",
  published: "#2563eb", pending_publish: "#7c3aed", candidate: "#64748b",
  selected: "#d97706", researching: "#0891b2", done: "#059669", discarded: "#94a3b8",
  running: "#d97706", success: "#059669", failed: "#dc2626", published_2: "#2563eb", removed: "#94a3b8",
};
const STATUS_LABELS: Record<string, string> = {
  draft: "草稿", in_review: "审核中", approved: "已批准", rejected: "已退回",
  published: "已发布", pending_publish: "待发布", candidate: "候选", selected: "已选定",
  researching: "研究中", done: "已完成", discarded: "已放弃",
  running: "运行中", success: "成功", failed: "失败", removed: "已下架",
};

export function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="badge">-</span>;
  return (
    <span className="badge" style={{ background: STATUS_COLORS[value] || "#475569" }}>
      {STATUS_LABELS[value] || value}
    </span>
  );
}

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="card">
      {(title || actions) && (
        <div className="card-head">
          {title && <h3>{title}</h3>}
          <div className="card-actions">{actions}</div>
        </div>
      )}
      {children}
    </div>
  );
}

export function Loading() { return <div className="state">加载中…</div>; }
export function ErrorBox({ msg, onRetry }: { msg: string; onRetry?: () => void }) {
  return (
    <div className="state error">
      ⚠ {msg}
      {onRetry && <button className="btn" onClick={onRetry}>重试</button>}
    </div>
  );
}
export function Empty({ msg = "暂无数据" }: { msg?: string }) { return <div className="state">{msg}</div>; }

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: "good" | "bad" }) {
  return (
    <div className={`stat ${tone || ""}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export function Msg({ ok, text }: { ok: boolean; text: string }) {
  return <div className={`msg ${ok ? "ok" : "err"}`}>{text}</div>;
}
