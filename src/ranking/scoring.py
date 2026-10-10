"""选题评分：LLM 打分 + 维度校验 + 分数钳制（不猜测、不入库不合格输出）。"""
from __future__ import annotations

import json
import re

from src.llm.client import LLMClient
from src.llm.prompts import SYSTEM_JSON, SCORE_TOPICS

DIMENSION_MAX = {"audience": 25, "reliability": 25, "differentiation": 20, "timeliness": 15, "fit": 15}
COLUMNS = ("全球 AI 前沿速递", "玄知深度拆解", "科技背后的生意")


def extract_json(text: str):
    """从 LLM 输出中提取 JSON（容忍代码块包裹）。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def total_score(scores: dict) -> float:
    return round(sum(scores.get(d, 0) for d in DIMENSION_MAX), 1)


def validate_topic(raw: dict, valid_ids: set[int]) -> dict | None:
    """校验单个选题输出；不合格返回 None（不入库，不猜测）。"""
    try:
        scores = raw.get("scores", {})
        clean_scores = {}
        for dim, cap in DIMENSION_MAX.items():
            value = float(scores.get(dim, 0))
            clean_scores[dim] = max(0.0, min(value, float(cap)))
        item_ids = [int(i) for i in raw.get("item_ids", []) if int(i) in valid_ids]
        title = str(raw.get("title", "")).strip()
        if len(title) < 6 or len(title) > 40 or not item_ids:
            return None
        column = str(raw.get("suggested_column", "")).strip()
        if column not in COLUMNS:
            column = "全球 AI 前沿速递"
        return {
            "title": title,
            "reason": str(raw.get("reason", ""))[:300],
            "scores": clean_scores,
            "score": total_score(clean_scores),
            "item_ids": sorted(set(item_ids)),
            "suggested_column": column,
        }
    except (TypeError, ValueError, AttributeError):
        return None


def score_topics(llm: LLMClient, items: list[dict], max_topics: int = 5) -> list[dict]:
    """items: [{id, title, source, summary}]。返回已校验的选题列表（按分数降序）。"""
    listing = "\n".join(
        f"{it['id']} | {it['source']} | {it['title'][:120]}" + (f" | {it['summary'][:150]}" if it.get("summary") else "")
        for it in items
    )
    reply = llm.chat([
        {"role": "system", "content": SYSTEM_JSON},
        {"role": "user", "content": SCORE_TOPICS.format(items=listing, max_topics=max_topics)},
    ], max_tokens=3000)
    raw_topics = extract_json(reply)
    if not isinstance(raw_topics, list):
        return []
    valid_ids = {it["id"] for it in items}
    results = [t for t in (validate_topic(r, valid_ids) for r in raw_topics) if t]
    results.sort(key=lambda t: t["score"], reverse=True)
    return results[:max_topics]
