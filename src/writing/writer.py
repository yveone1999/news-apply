"""文章创作：基于选题+研究档案生成中文稿件，版本化、幂等（不覆盖已批准版本）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.models import Article, ArticleVersion, ResearchRecord, Topic, utcnow
from src.llm.client import LLMClient
from src.llm.prompts import SYSTEM_JSON, WRITE_ARTICLE
from src.ranking.scoring import COLUMNS, extract_json


class ArticleConflictError(Exception):
    """该选题已有文章（不允许重复生成覆盖）。"""


def generate_article(
    llm: LLMClient,
    session: Session,
    topic: Topic,
    research: ResearchRecord,
    change_note: str = "初稿",
    force: bool = False,
    issues: list[str] | None = None,
) -> Article:
    """幂等：选题已有文章时——草稿/被退回可再生成新版本；已批准及之后的状态禁止覆盖。"""
    existing = session.execute(
        select(Article).where(Article.topic_id == topic.id)
    ).scalar_one_or_none()
    if existing and not force:
        if existing.status in ("approved", "pending_publish", "published"):
            raise ArticleConflictError(
                f"选题已有文章处于 {existing.status} 状态（id={existing.id}），不允许覆盖；请先废弃或人工处理"
            )
        article = existing
        version_no = article.current_version + 1
    elif existing and force:
        article = existing
        version_no = article.current_version + 1
    else:
        article = Article(topic_id=topic.id, column_name=topic.column_name, status="draft", title=topic.title)
        session.add(article)
        session.flush()
        version_no = 1

    reply = llm.chat([
        {"role": "system", "content": SYSTEM_JSON},
        {"role": "user", "content": WRITE_ARTICLE.format(
            column=topic.column_name,
            topic_title=topic.title,
            research=(research.content + ("\n\n结论: " + research.conclusion if research.conclusion else ""))
                   + (("\n\n上一版质量门禁发现的问题（必须逐条修正）:\n" + "\n".join(f"- {i}" for i in issues)) if issues else ""),
        )},
    ], max_tokens=6000)
    data = extract_json(reply)
    if not isinstance(data, dict) or not str(data.get("body", "")).strip():
        raise ValueError("写作输出无效（缺少正文）")

    article.title = str(data.get("title", topic.title))[:500]
    article.body = str(data.get("body", ""))
    article.summary = str(data.get("summary", ""))[:500] or None
    article.column_name = topic.column_name
    article.status = "draft"
    article.current_version = version_no
    session.add(ArticleVersion(
        article_id=article.id, version=version_no,
        title=article.title, body=article.body, change_note=change_note,
    ))
    session.commit()
    session.refresh(article)
    return article
