"""研究档案：基于已采集资讯生成事实卡片与证据链（只基于素材，不虚构）。"""
from __future__ import annotations

from src.llm.client import LLMClient
from src.llm.prompts import RESEARCH, SYSTEM_JSON
from src.ranking.scoring import extract_json


def build_research(llm: LLMClient, topic_title: str, items: list[dict]) -> dict:
    """items: [{id, title, link, source, published_at, summary}]。
    返回 {content, evidence[], open_questions[], conclusion, verified_count}。"""
    listing = "\n".join(
        f"- [{it['source']}] {it['title']}"
        + (f"\n  摘要: {it['summary'][:300]}" if it.get("summary") else "")
        + (f"\n  链接: {it['link']}" if it.get("link") else "")
        for it in items
    )
    reply = llm.chat([
        {"role": "system", "content": SYSTEM_JSON},
        {"role": "user", "content": RESEARCH.format(topic_title=topic_title, items=listing)},
    ], max_tokens=4000)
    data = extract_json(reply)
    if not isinstance(data, dict):
        raise ValueError("研究输出不是 JSON 对象")
    valid_urls = {it.get("link") for it in items if it.get("link")}
    evidence = []
    for ev in data.get("evidence", []):
        url = str(ev.get("source_url", "")).strip()
        evidence.append({
            "fact": str(ev.get("fact", ""))[:500],
            "source_title": str(ev.get("source_title", ""))[:200],
            "source_url": url if url in valid_urls else "",  # 链接必须在素材内，否则清空（不虚构来源）
            "verified": bool(ev.get("verified", False)) and url in valid_urls,
        })
    return {
        "content": str(data.get("content", "")),
        "evidence": evidence,
        "open_questions": [str(q)[:300] for q in data.get("open_questions", [])][:10],
        "conclusion": str(data.get("conclusion", ""))[:1000],
        "verified_count": sum(1 for e in evidence if e["verified"]),
    }
