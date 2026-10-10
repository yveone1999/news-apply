import { useState } from "react";
import { api } from "../api";
import { Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type LlmConfig = {
  base_url: string; model: string; timeout_seconds: string; max_retries: string; has_key: boolean;
};
type Setting = { key: string; value: string };
type BackupFile = { name: string; size_kb: number; created: string };

export default function Settings() {
  const llm = useFetch<LlmConfig>("/api/v1/llm/config");
  const settings = useFetch<{ count: number; items: Setting[] }>("/api/v1/settings");
  const backups = useFetch<{ count: number; items: BackupFile[] }>("/api/v1/backup/list");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [kv, setKv] = useState({ key: "", value: "" });
  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);
  const [backingUp, setBackingUp] = useState(false);

  async function testLlm() {
    setTesting(true);
    setTestResult("测试中…");
    try {
      const r = await api.post<{ ok: boolean; model: string; latency_ms: number; sample: string }>("/api/v1/llm/test");
      setTestResult(`连接成功：模型 ${r.model}，延迟 ${r.latency_ms}ms，回复样例「${r.sample}」`);
    } catch (e: any) {
      setTestResult(`连接失败：${e.message}`);
    } finally {
      setTesting(false);
    }
  }

  async function saveSetting() {
    if (!kv.key.trim()) { setAct({ ok: false, text: "请输入配置键" }); return; }
    try {
      await api.put("/api/v1/settings", { key: kv.key, value: kv.value });
      setAct({ ok: true, text: `已保存 ${kv.key}` });
      setKv({ key: "", value: "" });
      void settings.reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    }
  }

  async function runBackup() {
    setBackingUp(true);
    try {
      const r = await api.post<{ name: string; size_kb: number }>("/api/v1/backup/run");
      setAct({ ok: true, text: `备份完成：${r.name}（${r.size_kb} KB）` });
      void backups.reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    } finally {
      setBackingUp(false);
    }
  }

  return (
    <>
      <h1>系统设置</h1>
      {act && <Msg ok={act.ok} text={act.text} />}
      <Card title="大模型接口" actions={
        <button className="btn btn-primary" disabled={testing} onClick={testLlm}>
          {testing ? "测试中…" : "测试连接"}
        </button>
      }>
        {testResult && <div className={`msg ${testResult.startsWith("连接成功") ? "ok" : "err"}`}>{testResult}</div>}
        {!llm.data ? (llm.loading ? <Loading /> : llm.error ? <ErrorBox msg={llm.error} onRetry={llm.reload} /> : <Empty />) : (
          <table>
            <tbody>
              <tr><th style={{ width: 140 }}>接口地址</th><td>{llm.data.base_url || <span className="muted">未配置</span>}</td></tr>
              <tr><th>模型</th><td>{llm.data.model || <span className="muted">未配置</span>}</td></tr>
              <tr><th>超时（秒）</th><td>{llm.data.timeout_seconds}</td></tr>
              <tr><th>最大重试</th><td>{llm.data.max_retries}</td></tr>
              <tr><th>API Key</th><td>{llm.data.has_key ? "已配置（内容不展示）" : "未配置（当前接口免认证）"}</td></tr>
            </tbody>
          </table>
        )}
        <div className="muted" style={{ marginTop: 8 }}>修改配置请编辑项目根目录 .env 后重启服务（scripts/stop.sh && scripts/start.sh）。</div>
      </Card>

      <Card title="业务配置（键值对）">
        <div className="row">
          <label className="field" style={{ flex: "0 0 220px" }}>键
            <input value={kv.key} onChange={(e) => setKv({ ...kv, key: e.target.value })} placeholder="例如 daily_publish_count" />
          </label>
          <label className="field">值
            <input value={kv.value} onChange={(e) => setKv({ ...kv, value: e.target.value })} />
          </label>
          <div style={{ alignSelf: "flex-end" }}>
            <button className="btn btn-primary" onClick={saveSetting}>保存</button>
          </div>
        </div>
        {!settings.data ? (settings.loading ? <Loading /> : settings.error ? <ErrorBox msg={settings.error} onRetry={settings.reload} /> : null) :
          settings.data.items.length ? (
            <table style={{ marginTop: 12 }}>
              <thead><tr><th>键</th><th>值</th></tr></thead>
              <tbody>
                {settings.data.items.map((s) => <tr key={s.key}><td>{s.key}</td><td>{s.value}</td></tr>)}
              </tbody>
            </table>
          ) : <Empty msg="还没有业务配置" />}
      </Card>

      <Card title="数据备份" actions={
        <button className="btn btn-primary" disabled={backingUp} onClick={runBackup}>
          {backingUp ? "备份中…" : "立即备份"}
        </button>
      }>
        <div className="muted" style={{ marginBottom: 8 }}>
          备份保存在 storage/backups/。恢复方法：停止服务后，用备份文件覆盖 data/app.db（scripts/stop.sh → cp → scripts/start.sh）。
        </div>
        {!backups.data ? (backups.loading ? <Loading /> : backups.error ? <ErrorBox msg={backups.error} onRetry={backups.reload} /> : <Empty />) :
          backups.data.items.length ? (
            <table>
              <thead><tr><th>文件名</th><th>大小（KB）</th><th>创建时间</th></tr></thead>
              <tbody>
                {backups.data.items.map((b) => (
                  <tr key={b.name}><td>{b.name}</td><td>{b.size_kb}</td><td className="muted">{b.created}</td></tr>
                ))}
              </tbody>
            </table>
          ) : <Empty msg="还没有备份文件" />}
      </Card>
    </>
  );
}
