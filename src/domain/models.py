"""业务数据模型（12 个实体）。状态值约定见各字段注释。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class NewsSource(Base):
    __tablename__ = "news_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    url: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(20), default="rss")  # rss | atom | web
    lang: Mapped[str] = mapped_column(String(8), default="en")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("news_sources.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    link: Mapped[str | None] = mapped_column(String(800))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256(规范化标题+链接)
    lang: Mapped[str] = mapped_column(String(8), default="en")
    raw: Mapped[str | None] = mapped_column(Text)  # 原始条目 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Topic(Base):
    __tablename__ = "topics"
    # status: candidate | selected | researching | done | discarded
    __table_args__ = (UniqueConstraint("title", "column_name", name="uq_topic_title_column"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    news_item_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id"), index=True)
    column_name: Mapped[str] = mapped_column(String(50))  # 全球 AI 前沿速递 | 玄知深度拆解 | 科技背后的生意
    score: Mapped[float | None] = mapped_column(Float)  # 0-100
    score_detail: Mapped[str | None] = mapped_column(Text)  # JSON: 各维度得分
    status: Mapped[str] = mapped_column(String(20), default="candidate", index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ResearchRecord(Base):
    __tablename__ = "research_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    content: Mapped[str] = mapped_column(Text)  # 研究档案正文
    evidence: Mapped[str | None] = mapped_column(Text)  # JSON: [{fact, source_title, source_url, verified}]
    open_questions: Mapped[str | None] = mapped_column(Text)  # JSON: [str]
    conclusion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Article(Base):
    __tablename__ = "articles"
    # status: draft | in_review | approved | rejected | pending_publish | published
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str | None] = mapped_column(String(500))
    column_name: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    versions: Mapped[list["ArticleVersion"]] = relationship(back_populates="article", order_by="ArticleVersion.version")


class ArticleVersion(Base):
    __tablename__ = "article_versions"
    __table_args__ = (UniqueConstraint("article_id", "version", name="uq_article_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    change_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    article: Mapped[Article] = relationship(back_populates="versions")


class MediaAsset(Base):
    __tablename__ = "media_assets"
    # usage: cover | body
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), index=True)
    path: Mapped[str] = mapped_column(String(800))
    media_type: Mapped[str] = mapped_column(String(20), default="image")
    source_name: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(800))
    license_note: Mapped[str | None] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(String(500))
    usage: Mapped[str] = mapped_column(String(20), default="body")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewRecord(Base):
    __tablename__ = "review_records"
    # result: pass | fail | revise
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    reviewer: Mapped[str] = mapped_column(String(100), default="human")
    result: Mapped[str] = mapped_column(String(20))
    issues: Mapped[str | None] = mapped_column(Text)  # JSON: [str]
    note: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublishingRecord(Base):
    __tablename__ = "publishing_records"
    # status: published | removed
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    platform: Mapped[str] = mapped_column(String(50), default="toutiao")
    url: Mapped[str] = mapped_column(String(800))
    status: Mapped[str] = mapped_column(String(20), default="published")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ArticleMetric(Base):
    __tablename__ = "article_metrics"
    __table_args__ = (UniqueConstraint("article_id", "stat_date", name="uq_article_metric_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    stat_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    reads: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    # status: running | success | failed
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    input_json: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppSetting(Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
