"""质量门禁：规则检查（确定性）+ LLM 事实核查。全部问题落库，供人工审核参考。"""
from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.models import Article, ResearchRecord
from src.llm.client import LLMClient
from src.llm.prompts import QUALITY_CHECK, SYSTEM_JSON
from src.ranking.scoring import extract_json

# 规则检查用词表（广告法/平台风险）
ABSOLUTE_WORDS = ["最先进", "世界第一", "全球第一", "国家级", "100%", "绝对", "彻底解决", "稳赚", "必涨", "震惊", "速看"]
HEDGE_WORDS = ["据报道", "据称", "尚未证实", "未证实", "消息称", "或", "可能", "预计", "爆料"]


def rule_checks(article: Article, session: Session) -> list[str]:
    issues = []
    title = article.title or ""
    if not (8 <= len(title) <= 30):
        issues.append(f"标题长度 {len(title)} 字，建议 8-30 字")
    for word in ABSOLUTE_WORDS:
        if word in title or word in (article.body or ""):
            issues.append(f"含风险用语「{word}」，需删除或改写")
    body_len = len(article.body or "")
    if body_len < 400:
        issues.append(f"正文仅 {body_len} 字，低于最低 400 字")
    if body_len > 3000:
        issues.append(f"正文 {body_len} 字，超过 3000 字上限，建议拆分")
    if not (article.body or "").strip().endswith(("？", "?")):
        issues.append("结尾缺少互动问题（建议以开放式问句收尾）")
    # 重复度：与既有文章标题完全相同
    dup = session.execute(
        select(Article.title).where(
            Article.title == title, Article.id != article.id
        )
    ).scalar_one_or_none()
    if dup:
        issues.append(f"标题与既有文章重复：{dup}")
    return issues


def llm_fact_check(llm: LLMClient, article: Article, research: ResearchRecord) -> dict:
    research_text = research.content[:6000]
    if research.evidence:
        research_text += "\n证据:\n" + json.dumps(json.loads(research.evidence), ensure_ascii=False, indent=1)[:4000]
    reply = llm.chat([
        {"role": "system", "content": SYSTEM_JSON},
        {"role": "user", "content": QUALITY_CHECK.format(
            title=article.title, body=(article.body or "")[:8000], research=research_text
        )},
    ], max_tokens=3000)
    data = extract_json(reply)
    if not isinstance(data, dict):
        return {"facts": [], "unsupported": [], "unmarked_uncertainty": [], "logic": [], "comment": "核查输出解析失败，需人工全量核查"}
    return {
        "facts": data.get("facts", []),
        "unsupported": [str(x) for x in data.get("unsupported", [])][:20],
        "unmarked_uncertainty": [str(x) for x in data.get("unmarked_uncertainty", [])][:20],
        "logic": [str(x) for x in data.get("logic", [])][:20],
        "comment": str(data.get("comment", ""))[:300],
    }


def run_quality_gate(llm: LLMClient, session: Session, article: Article, research: ResearchRecord) -> dict:
    """执行完整门禁，写回 article.quality_report（JSON）。返回报告。"""
    issues = rule_checks(article, session)
    fact_check = llm_fact_check(llm, article, research)

    # 硬门禁：研究证据不足
    evidence_count = len(json.loads(research.evidence or "[]"))
    if evidence_count < 1:
        issues.append("硬门禁：研究档案没有任何事实证据，不可进入发布审核")

    # 未标注不确定性内容 → 风险项
    for item in fact_check["unmarked_uncertainty"]:
        issues.append(f"未标注不确定性的表述：{item}")
    for item in fact_check["unsupported"]:
        issues.append(f"研究档案无依据的陈述：{item}")
    for item in fact_check["logic"]:
        issues.append(f"逻辑问题：{item}")

    report = {
        "passed": not issues,
        "issues": issues,
        "fact_check": fact_check,
        "evidence_count": evidence_count,
        "checked_at": "now",
    }
    article.quality_report = json.dumps(report, ensure_ascii=False)
    session.commit()
    session.refresh(article)
    return report
