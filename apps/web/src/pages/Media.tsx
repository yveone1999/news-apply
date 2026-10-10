import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Badge, Card, Empty, ErrorBox, Loading, Msg, useFetch } from "../components";

type Media = {
  id: number; article_id: number | null; path: string; source_name: string | null;
  source_url: string | null; license_note: string | null; caption: string | null; usage: string;
};

const EMPTY_FORM = { article_id: "", source_name: "", source_url: "", license_note: "", caption: "", usage: "body" as "body" | "cover" };

export default function Media() {
  const { data, loading, error, reload } = useFetch<{ count: number; items: Media[] }>("/api/v1/media");
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState<File | null>(null);
  const [act, setAct] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload() {
    if (!file) { setAct({ ok: false, text: "请选择图片文件" }); return; }
    if (!form.license_note.trim() && !form.source_name.trim()) {
      setAct({ ok: false, text: "必须记录来源（source_name）或授权依据（license_note）" });
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    if (form.article_id) fd.append("article_id", form.article_id);
    fd.append("source_name", form.source_name);
    fd.append("source_url", form.source_url);
    fd.append("license_note", form.license_note);
    fd.append("caption", form.caption);
    fd.append("usage", form.usage);
    setBusy(true);
    setAct(null);
    try {
      await api.upload("/api/v1/media", fd);
      setAct({ ok: true, text: "上传成功" });
      setFile(null);
      setForm(EMPTY_FORM);
      void reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  async function remove(mid: number) {
    if (!window.confirm(`确认删除图片 #${mid}？文件将被移除且不可恢复。`)) return;
    try {
      await api.del(`/api/v1/media/${mid}`);
      void reload();
    } catch (e: any) {
      setAct({ ok: false, text: e.message });
    }
  }

  return (
    <>
      <h1>图片素材</h1>
      {act && <Msg ok={act.ok} text={act.text} />}
      <Card title="上传新图片（必须记录来源或授权依据）">
        <div className="row">
          <label className="field" style={{ flex: "0 0 150px" }}>关联文章 ID
            <input value={form.article_id} onChange={(e) => setForm({ ...form, article_id: e.target.value })} placeholder="可选" />
          </label>
          <label className="field">来源名称（如：Reuters / 官网截图）
            <input value={form.source_name} onChange={(e) => setForm({ ...form, source_name: e.target.value })} />
          </label>
          <label className="field">来源链接
            <input value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} placeholder="可选" />
          </label>
        </div>
        <div className="row">
          <label className="field">授权 / 使用依据
            <input value={form.license_note} onChange={(e) => setForm({ ...form, license_note: e.target.value })} placeholder="例如：官方新闻稿配图，允许报道使用" />
          </label>
          <label className="field">图注
            <input value={form.caption} onChange={(e) => setForm({ ...form, caption: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "0 0 120px" }}>用途
            <select value={form.usage} onChange={(e) => setForm({ ...form, usage: e.target.value as "body" | "cover" })}>
              <option value="body">正文配图</option>
              <option value="cover">封面</option>
            </select>
          </label>
        </div>
        <div className="row">
          <label className="field">图片文件
            <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </label>
          <div style={{ alignSelf: "flex-end" }}>
            <button className="btn btn-primary" disabled={busy} onClick={upload}>{busy ? "上传中…" : "上传"}</button>
          </div>
        </div>
      </Card>

      <Card title={`素材库（${data?.count ?? 0}）`}>
        {!data ? (loading ? <Loading /> : error ? <ErrorBox msg={error} onRetry={reload} /> : <Empty />) :
          data.items.length ? (
            <div className="media-grid">
              {data.items.map((m) => (
                <div className="media-card" key={m.id}>
                  <img src={`/media-files/${m.path.split("/").pop()}`} alt={m.caption || `素材 ${m.id}`} />
                  <div style={{ fontSize: 13 }}>{m.caption || <span className="muted">（无图注）</span>}</div>
                  <div className="muted">
                    来源：{m.source_name || "-"}{m.license_note ? ` · ${m.license_note}` : ""}
                  </div>
                  <div className="muted" style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
                    <Badge value={m.usage === "cover" ? "published" : "candidate"} />
                    <span>{m.usage === "cover" ? "封面" : "正文配图"}</span>
                    {m.article_id && <Link to={`/articles/${m.article_id}`}>文章 #{m.article_id}</Link>}
                  </div>
                  <button className="btn btn-sm btn-danger" style={{ marginTop: 6 }} onClick={() => remove(m.id)}>删除</button>
                </div>
              ))}
            </div>
          ) : <Empty msg="还没有素材" />}
      </Card>
    </>
  );
}
