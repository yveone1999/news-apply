"""阶段 C 路由：选题 / 研究 / 文章 / 质量门禁 / 状态流转。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.models import Article, ArticleVersion, NewsItem, NewsSource, ReviewRecord, ResearchRecord, Topic, WorkflowRun, utcnow
from src.llm.client import LLMClient
from src.quality.gates import run_quality_gate
from src.ranking.scoring import COLUMNS, score_topics
from src.research.research import build_research
from src.workflows.runs import ConflictError, finish_run, start_run
from src.writing.writer import ArticleConflictError, generate_article

class GenerateTopicsIn(BaseModel):
    max_topics: int = Field(default=5, ge=1, le=10)
    hours: int = Field(default=24, ge=1, le=72)


class GenerateArticleIn(BaseModel):
    topic_id: int
    change_note: str | None = None
    issues: list[str] | None = None  # 上一版门禁问题（退回修改时传入）


class ReviewIn(BaseModel):
    reviewer: str = "human"
    note: str | None = None
    issues: list[str] | None = None


def build_routes(get_db, get_llm) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["content"])

    @r.get("/topics")
    def list_topics(status: str | None = None, column_name: str | None = None,
                    min_score: float | None = None, limit: int = Query(50, le=200),
                    db: Session = Depends(get_db)):
        q = select(Topic).order_by(Topic.score.desc().nullslast(), Topic.id.desc())
        if status:
            q = q.where(Topic.status == status)
        if column_name:
            q = q.where(Topic.column_name == column_name)
        if min_score is not None:
            q = q.where(Topic.score >= min_score)
        rows = db.execute(q.limit(limit)).scalars().all()
        return {"count": len(rows), "items": [
            {"id": t.id, "title": t.title, "column_name": t.column_name, "score": t.score,
             "status": t.status, "item_ids": json.loads(t.item_ids or "[]"),
             "created_at": t.created_at.isoformat()}
            for t in rows
        ]}

    @r.post("/topics/generate")
    def topics_generate(body: GenerateTopicsIn, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=body.hours)
        rows = db.execute(
            select(NewsItem, NewsSource.name)
            .join(NewsSource, NewsItem.source_id == NewsSource.id)
            .where(NewsItem.published_at >= cutoff)
            .order_by(NewsItem.published_at.desc())
            .limit(150)
        ).all()
        if not rows:
            raise HTTPException(400, f"近 {body.hours} 小时没有已采集资讯，请先运行采集")
        items = [{"id": it.id, "title": it.title, "source": src_name, "summary": it.summary} for it, src_name in rows]
        try:
            run = start_run(db, "score_topics", idempotency_key=None, input_data={"hours": body.hours, "items": len(items)})
        except ConflictError as exc:
            raise HTTPException(409, str(exc))
        try:
            results = score_topics(llm, items, max_topics=body.max_topics)
        except Exception as exc:  # noqa: BLE001
            finish_run(db, run, ok=False, error=f"{type(exc).__name__}: {exc}")
            raise HTTPException(502, f"选题生成失败: {type(exc).__name__}") from exc
        created = []
        for t in results:
            if db.execute(select(Topic).where(Topic.title == t["title"])).scalar_one_or_none():
                continue
            db.add(Topic(
                title=t["title"], column_name=t["suggested_column"], score=t["score"],
                score_detail=json.dumps({"reason": t["reason"], "scores": t["scores"]}, ensure_ascii=False),
                item_ids=json.dumps(t["item_ids"]),
                news_item_id=t["item_ids"][0], status="candidate",
            ))
            created.append(t)
        db.commit()
        finish_run(db, run, ok=True, output={"created": len(created), "topics": created})
        return {"run_id": run.id, "created": len(created), "topics": created}

    @r.post("/topics/{topic_id}/research")
    def topic_research(topic_id: int, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
        topic = db.get(Topic, topic_id)
        if not topic:
            raise HTTPException(404, "选题不存在")
        item_ids = json.loads(topic.item_ids or "[]")
        if not item_ids:
            raise HTTPException(400, "选题没有关联资讯，无法研究")
        items_rows = db.execute(select(NewsItem).where(NewsItem.id.in_(item_ids))).scalars().all()
        items = [{"id": it.id, "title": it.title, "link": it.link, "summary": it.summary,
                  "published_at": it.published_at.isoformat() if it.published_at else None,
                  "source": str(it.source_id)} for it in items_rows]
        run = start_run(db, "research", idempotency_key=None, input_data={"topic_id": topic_id})
        try:
            result = build_research(llm, topic.title, items)
        except Exception as exc:  # noqa: BLE001
            finish_run(db, run, ok=False, error=f"{type(exc).__name__}: {exc}")
            raise HTTPException(502, f"研究失败: {type(exc).__name__}") from exc
        record = ResearchRecord(
            topic_id=topic_id,
            content=result["content"],
            evidence=json.dumps(result["evidence"], ensure_ascii=False),
            open_questions=json.dumps(result["open_questions"], ensure_ascii=False),
            conclusion=result["conclusion"],
        )
        db.add(record)
        topic.status = "researching"
        db.commit()
        db.refresh(record)
        finish_run(db, run, ok=True, output={"research_id": record.id, "verified_count": result["verified_count"]})
        return {"run_id": run.id, "research_id": record.id, **{k: result[k] for k in ("content", "evidence", "open_questions", "conclusion", "verified_count")}}

    @r.get("/research")
    def list_research(topic_id: int | None = None, limit: int = Query(20, le=100), db: Session = Depends(get_db)):
        q = select(ResearchRecord).order_by(ResearchRecord.id.desc())
        if topic_id:
            q = q.where(ResearchRecord.topic_id == topic_id)
        rows = db.execute(q.limit(limit)).scalars().all()
        return {"count": len(rows), "items": [
            {"id": rec.id, "topic_id": rec.topic_id, "conclusion": rec.conclusion,
             "evidence_count": len(json.loads(rec.evidence or "[]")),
             "created_at": rec.created_at.isoformat()}
            for rec in rows
        ]}

    @r.post("/articles/generate")
    def articles_generate(body: GenerateArticleIn, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
        topic = db.get(Topic, body.topic_id)
        if not topic:
            raise HTTPException(404, "选题不存在")
        research = db.execute(
            select(ResearchRecord).where(ResearchRecord.topic_id == topic.id).order_by(ResearchRecord.id.desc())
        ).scalars().first()
        if not research:
            raise HTTPException(409, "该选题还没有研究档案，请先运行研究")
        run = start_run(db, "write_article", idempotency_key=None, input_data={"topic_id": topic.id})
        try:
            article = generate_article(llm, db, topic, research,
                             change_note=body.change_note or ("修正版：处理门禁问题" if body.issues else "初稿"),
                             issues=body.issues)
        except ArticleConflictError as exc:
            finish_run(db, run, ok=False, error=str(exc))
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            finish_run(db, run, ok=False, error=f"{type(exc).__name__}: {exc}")
            raise HTTPException(502, f"写作失败: {type(exc).__name__}") from exc
        topic.status = "done"
        db.commit()
        finish_run(db, run, ok=True, output={"article_id": article.id, "version": article.current_version})
        return {"run_id": run.id, "article_id": article.id, "version": article.current_version,
                "title": article.title, "status": article.status}

    @r.get("/articles")
    def list_articles(status: str | None = None, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
        q = select(Article).order_by(Article.id.desc())
        if status:
            q = q.where(Article.status == status)
        rows = db.execute(q.limit(limit)).scalars().all()
        return {"count": len(rows), "items": [
            {"id": a.id, "topic_id": a.topic_id, "title": a.title, "column_name": a.column_name,
             "status": a.status, "current_version": a.current_version,
             "quality_passed": (json.loads(a.quality_report).get("passed") if a.quality_report else None),
             "updated_at": a.updated_at.isoformat()}
            for a in rows
        ]}

    @r.get("/articles/{article_id}")
    def get_article(article_id: int, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        versions = db.execute(
            select(ArticleVersion).where(ArticleVersion.article_id == article_id).order_by(ArticleVersion.version)
        ).scalars().all()
        return {
            "id": article.id, "topic_id": article.topic_id, "title": article.title,
            "summary": article.summary, "column_name": article.column_name, "status": article.status,
            "body": article.body, "current_version": article.current_version,
            "quality_report": json.loads(article.quality_report) if article.quality_report else None,
            "versions": [{"version": v.version, "title": v.title, "change_note": v.change_note,
                          "created_at": v.created_at.isoformat()} for v in versions],
        }

    @r.post("/articles/{article_id}/quality-check")
    def article_quality_check(article_id: int, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        research = db.execute(
            select(ResearchRecord).where(ResearchRecord.topic_id == article.topic_id).order_by(ResearchRecord.id.desc())
        ).scalars().first()
        if not research:
            raise HTTPException(409, "找不到研究档案，无法执行事实核查")
        run = start_run(db, "quality_check", idempotency_key=None, input_data={"article_id": article_id})
        try:
            report = run_quality_gate(llm, db, article, research)
        except Exception as exc:  # noqa: BLE001
            finish_run(db, run, ok=False, error=f"{type(exc).__name__}: {exc}")
            raise HTTPException(502, f"质量门禁失败: {type(exc).__name__}") from exc
        finish_run(db, run, ok=True, output={"passed": report["passed"], "issues": len(report["issues"])})
        return {"run_id": run.id, **report}

    # ---------- 状态流转（审批与发布分离）----------

    @r.post("/articles/{article_id}/submit")
    def article_submit(article_id: int, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        if article.status not in ("draft", "rejected"):
            raise HTTPException(409, f"当前状态 {article.status} 不可提交审核")
        if not article.quality_report or not json.loads(article.quality_report).get("passed"):
            raise HTTPException(409, "质量门禁未通过（或尚未执行），不可提交人工审核")
        article.status = "in_review"
        db.commit()
        return {"id": article.id, "status": article.status}

    @r.post("/articles/{article_id}/approve")
    def article_approve(article_id: int, body: ReviewIn, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        if article.status != "in_review":
            raise HTTPException(409, f"当前状态 {article.status} 不可审批")
        article.status = "approved"
        db.add(ReviewRecord(article_id=article.id, reviewer=body.reviewer, result="pass",
                            note=body.note, approved_at=utcnow()))
        db.commit()
        return {"id": article.id, "status": article.status}

    @r.post("/articles/{article_id}/reject")
    def article_reject(article_id: int, body: ReviewIn, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        if article.status != "in_review":
            raise HTTPException(409, f"当前状态 {article.status} 不可驳回")
        article.status = "rejected"
        db.add(ReviewRecord(article_id=article.id, reviewer=body.reviewer, result="fail",
                            issues=json.dumps(body.issues or [], ensure_ascii=False), note=body.note))
        db.commit()
        return {"id": article.id, "status": article.status}

    @r.post("/articles/{article_id}/reedit")
    def article_reedit(article_id: int, db: Session = Depends(get_db)):
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(404, "文章不存在")
        if article.status != "rejected":
            raise HTTPException(409, f"当前状态 {article.status} 不可重新编辑")
        article.status = "draft"
        db.commit()
        return {"id": article.id, "status": article.status}

    return r
