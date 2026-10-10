"""阶段 D 路由：发布记录 / 收益录入 / 素材 / 备份 / 看板 / 分析 / 编辑与版本恢复。"""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.collectors.feeds import fetch_feed, parse_entries
from src.domain.models import (
    Article, ArticleMetric, ArticleVersion, AppSetting, MediaAsset,
    NewsItem, NewsSource, PublishingRecord, ReviewRecord, ResearchRecord,
    Topic, WorkflowRun, utcnow,
)
from src.domain.db import resolve_db_url
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = PROJECT_ROOT / "storage" / "backups"


class PublishIn(BaseModel):
    url: str = Field(min_length=5)
    platform: str = "toutiao"
    note: str | None = None


class MetricsIn(BaseModel):
    stat_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reads: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    revenue: float | None = None
    note: str | None = None


class ArticleEditIn(BaseModel):
    title: str | None = None
    body: str | None = None
    summary: str | None = None
    change_note: str | None = None


class SettingIn(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = ""


def build_routes(get_db) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["ops"])

    # ---------- 文章编辑与版本 ----------

    @r.put("/articles/{article_id}")
    def edit_article(article_id: int, body: ArticleEditIn, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        if article.status not in ("draft", "rejected"):
            raise HTTPException(409, f"当前状态 {article.status} 不可编辑（仅草稿/被退回可编辑）")
        changes = body.model_dump(exclude_none=True)
        if "title" in changes:
            article.title = changes["title"][:500]
        if "body" in changes:
            article.body = changes["body"]
        if "summary" in changes:
            article.summary = changes["summary"][:500]
        article.current_version += 1
        article.quality_report = None  # 内容变更，门禁报告失效
        db.add(ArticleVersion(
            article_id=article.id, version=article.current_version,
            title=article.title, body=article.body,
            change_note=(body.change_note or "人工编辑")[:500],
        ))
        db.commit()
        return {"id": article.id, "current_version": article.current_version}

    @r.post("/articles/{article_id}/versions/{version}/restore")
    def restore_version(article_id: int, version: int, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        if article.status not in ("draft", "rejected"):
            raise HTTPException(409, f"当前状态 {article.status} 不可恢复版本")
        target = db.execute(
            select(ArticleVersion).where(ArticleVersion.article_id == article_id, ArticleVersion.version == version)
        ).scalar_one_or_none()
        if not target:
            raise HTTPException(404, "版本不存在")
        article.title, article.body = target.title, target.body
        article.current_version += 1
        article.quality_report = None
        db.add(ArticleVersion(article_id=article.id, version=article.current_version,
                              title=target.title, body=target.body, change_note=f"恢复自 v{version}"))
        db.commit()
        return {"id": article.id, "current_version": article.current_version}

    # ---------- 发布记录（人工发布后回填）----------

    @r.post("/articles/{article_id}/publish")
    def publish_article(article_id: int, body: PublishIn, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        if article.status != "approved":
            raise HTTPException(409, f"只有 approved 状态可记录发布，当前 {article.status}")
        rec = PublishingRecord(article_id=article.id, platform=body.platform, url=body.url, note=body.note)
        db.add(rec)
        article.status = "published"
        db.commit()
        return {"article_id": article.id, "status": article.status, "publish_url": body.url}

    @r.get("/publishing")
    def list_publishing(limit: int = Query(100, le=500), db: Session = Depends(get_db)):
        rows = db.execute(
            select(PublishingRecord, Article.title).join(Article, PublishingRecord.article_id == Article.id)
            .order_by(PublishingRecord.id.desc()).limit(limit)
        ).all()
        return {"count": len(rows), "items": [
            {"id": p.id, "article_id": p.article_id, "title": t, "platform": p.platform, "url": p.url,
             "status": p.status, "published_at": p.published_at.isoformat(), "note": p.note}
            for p, t in rows
        ]}

    # ---------- 收益与阅读数据 ----------

    @r.post("/articles/{article_id}/metrics")
    def upsert_metrics(article_id: int, body: MetricsIn, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        existing = db.execute(
            select(ArticleMetric).where(
                ArticleMetric.article_id == article_id, ArticleMetric.stat_date == body.stat_date
            )
        ).scalar_one_or_none()
        if existing:
            for f in ("reads", "likes", "comments", "shares", "revenue", "note"):
                v = getattr(body, f)
                if v is not None:
                    setattr(existing, f, v)
        else:
            db.add(ArticleMetric(article_id=article_id, **body.model_dump()))
        db.commit()
        return {"article_id": article_id, "stat_date": body.stat_date, "updated": True}

    @r.get("/articles/{article_id}/metrics")
    def get_metrics(article_id: int, db: Session = Depends(get_db)):
        rows = db.execute(
            select(ArticleMetric).where(ArticleMetric.article_id == article_id).order_by(ArticleMetric.stat_date)
        ).scalars().all()
        return {"count": len(rows), "items": [
            {"stat_date": m.stat_date, "reads": m.reads, "likes": m.likes, "comments": m.comments,
             "shares": m.shares, "revenue": m.revenue, "note": m.note} for m in rows
        ]}

    # ---------- 图片素材 ----------

    @r.get("/media")
    def list_media(article_id: int | None = None, db: Session = Depends(get_db)):
        q = select(MediaAsset).order_by(MediaAsset.id.desc())
        if article_id:
            q = q.where(MediaAsset.article_id == article_id)
        rows = db.execute(q.limit(200)).scalars().all()
        return {"count": len(rows), "items": [
            {"id": m.id, "article_id": m.article_id, "path": m.path, "source_name": m.source_name,
             "source_url": m.source_url, "license_note": m.license_note, "caption": m.caption,
             "usage": m.usage} for m in rows
        ]}

    @r.post("/media", status_code=201)
    async def upload_media(
        file: UploadFile = File(...),
        article_id: int | None = Form(None),
        source_name: str | None = Form(None),
        source_url: str | None = Form(None),
        license_note: str | None = Form(None),
        caption: str | None = Form(None),
        usage: str = Form("body"),
        db: Session = Depends(get_db),
    ):
        if not license_note and not source_name:
            raise HTTPException(400, "图片必须记录来源或授权依据（license_note 或 source_name）")
        img_dir = PROJECT_ROOT / "storage" / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(file.filename or "img.png").suffix or ".png"
        dest = img_dir / f"{utcnow().strftime('%Y%m%d-%H%M%S')}-{utcnow().microsecond}{suffix}"
        with open(dest, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        asset = MediaAsset(
            article_id=article_id, path=str(dest.relative_to(PROJECT_ROOT)),
            source_name=source_name, source_url=source_url, license_note=license_note,
            caption=caption, usage=usage if usage in ("cover", "body") else "body",
        )
        db.add(asset)
        db.commit()
        return {"id": asset.id, "path": asset.path}

    @r.delete("/media/{media_id}")
    def delete_media(media_id: int, db: Session = Depends(get_db)):
        asset = db.get(MediaAsset, media_id)
        if not asset:
            raise HTTPException(404, "素材不存在")
        if asset.path:
            fp = PROJECT_ROOT / asset.path
            if fp.exists():
                fp.unlink()
        db.delete(asset)
        db.commit()
        return {"deleted": media_id}

    # ---------- 看板与分析 ----------

    @r.get("/dashboard/overview")
    def overview(db: Session = Depends(get_db)):
        def count(entity, where=None):
            q = select(func.count()).select_from(entity)
            if where is not None:
                q = q.where(where)
            return db.execute(q).scalars().first() or 0
        today = utcnow().strftime("%Y-%m-%d")
        metrics = db.execute(select(ArticleMetric)).scalars().all()
        today_runs = db.execute(
            select(WorkflowRun).where(WorkflowRun.started_at >= datetime.fromisoformat(today))
        ).scalars().all()
        failed_runs = [x for x in today_runs if x.status == "failed"]
        return {
            "pending_review": count(Article, Article.status == "in_review"),
            "drafts": count(Article, Article.status == "draft"),
            "published_total": count(Article, Article.status == "published"),
            "news_last_24h": count(NewsItem, NewsItem.published_at >= datetime.now(timezone.utc) - timedelta(hours=24)),
            "topics_candidate": count(Topic, Topic.status == "candidate"),
            "reads_total": sum(m.reads or 0 for m in metrics),
            "engagements_total": sum((m.likes or 0) + (m.comments or 0) + (m.shares or 0) for m in metrics),
            "revenue_total": round(sum(m.revenue or 0 for m in metrics), 2),
            "runs_today": len(today_runs),
            "failed_runs_today": len(failed_runs),
            "failed_runs": [{"id": x.id, "run_type": x.run_type, "error": (x.error or "")[:200]} for x in failed_runs[:10]],
        }

    @r.get("/analytics/columns")
    def columns(db: Session = Depends(get_db)):
        articles = db.execute(select(Article)).scalars().all()
        metrics = db.execute(select(ArticleMetric)).scalars().all()
        by_article: dict[int, dict] = {}
        for m in metrics:
            agg = by_article.setdefault(m.article_id, {"reads": 0, "eng": 0, "revenue": 0.0})
            agg["reads"] += m.reads or 0
            agg["eng"] += (m.likes or 0) + (m.comments or 0) + (m.shares or 0)
            agg["revenue"] += m.revenue or 0
        result = {}
        for a in articles:
            col = a.column_name or "未分类"
            row = result.setdefault(col, {"articles": 0, "published": 0, "reads": 0, "engagements": 0, "revenue": 0.0})
            row["articles"] += 1
            if a.status == "published":
                row["published"] += 1
            agg = by_article.get(a.id)
            if agg:
                row["reads"] += agg["reads"]
                row["engagements"] += agg["eng"]
                row["revenue"] += agg["revenue"]
        for row in result.values():
            row["revenue"] = round(row["revenue"], 2)
        return {"columns": result}

    @r.get("/analytics/trend")
    def trend(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
        start = (utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = db.execute(select(ArticleMetric).where(ArticleMetric.stat_date >= start)).scalars().all()
        by_day: dict[str, dict] = {}
        for m in rows:
            d = by_day.setdefault(m.stat_date, {"reads": 0, "engagements": 0, "revenue": 0.0})
            d["reads"] += m.reads or 0
            d["engagements"] += (m.likes or 0) + (m.comments or 0) + (m.shares or 0)
            d["revenue"] += m.revenue or 0
        for d in by_day.values():
            d["revenue"] = round(d["revenue"], 2)
        return {"days": days, "series": [
            {"stat_date": k, **by_day[k]} for k in sorted(by_day)
        ]}

    # ---------- 资讯源连通性测试 ----------

    @r.post("/news-sources/{source_id}/test")
    def test_source(source_id: int, db: Session = Depends(get_db)):
        source = db.get(NewsSource, source_id)
        if not source:
            raise HTTPException(404, "来源不存在")
        try:
            xml_text = fetch_feed(source.url)
            items = parse_entries(xml_text, source)
            return {"ok": True, "count": len(items)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # ---------- 模型配置与备份 ----------

    @r.get("/llm/config")
    def llm_config():
        return {
            "base_url": os.environ.get("LLM_BASE_URL", ""),
            "model": os.environ.get("LLM_MODEL", ""),
            "timeout_seconds": os.environ.get("LLM_TIMEOUT_SECONDS", "120"),
            "max_retries": os.environ.get("LLM_MAX_RETRIES", "3"),
            "has_key": bool(os.environ.get("LLM_API_KEY")),
        }

    @r.get("/settings")
    def get_settings(db: Session = Depends(get_db)):
        rows = db.execute(select(AppSetting).order_by(AppSetting.key)).scalars().all()
        return {"count": len(rows), "items": [{"key": s.key, "value": s.value} for s in rows]}

    @r.put("/settings")
    def put_setting(body: SettingIn, db: Session = Depends(get_db)):
        existing = db.execute(select(AppSetting).where(AppSetting.key == body.key)).scalar_one_or_none()
        if existing:
            existing.value = body.value
        else:
            db.add(AppSetting(key=body.key, value=body.value))
        db.commit()
        return {"key": body.key, "saved": True}

    @r.get("/backup/list")
    def backup_list():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(BACKUP_DIR.glob("app-*.db"), reverse=True)
        return {"count": len(files), "items": [
            {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1),
             "created": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()}
            for f in files
        ]}

    @r.post("/backup/run")
    def backup_run():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        db_url = resolve_db_url(os.environ.get("DB_URL", "sqlite:///data/app.db"))
        if not db_url.startswith("sqlite:///"):
            raise HTTPException(400, "备份目前仅支持 SQLite")
        src_path = db_url[len("sqlite:///"):]
        if not Path(src_path).exists():
            raise HTTPException(404, "数据库文件不存在")
        dest = BACKUP_DIR / f"app-{utcnow().strftime('%Y%m%d-%H%M%S')}.db"
        dst = sqlite3.connect(dest)
        with sqlite3.connect(src_path) as src:
            src.backup(dst)
        dst.close()
        return {"name": dest.name, "size_kb": round(dest.stat().st_size / 1024, 1)}

    return r
