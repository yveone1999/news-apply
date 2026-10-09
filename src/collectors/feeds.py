"""资讯采集：抓取 RSS/Atom，规范化，按内容哈希去重入库。失败只记录，不虚构内容。"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import NewsItem, NewsSource

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) XuanZhiContentEngine/0.1"}


def fetch_feed(url: str, timeout: float = 25.0) -> str:
    last_err: Exception | None = None
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.0)
    assert last_err is not None
    raise last_err


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _published(entry) -> datetime | None:
    ts = entry.get("published_parsed") or entry.get("updated_parsed")
    if ts:
        return datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc)
    return None


def content_hash(title: str, link: str) -> str:
    norm = re.sub(r"\s+", " ", (title or "").strip().lower())
    key = f"{norm}|{(link or '').strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_entries(xml_text: str, source: NewsSource) -> list[dict]:
    parsed = feedparser.parse(xml_text)
    items = []
    for entry in parsed.entries:
        title = _clean(entry.get("title"))
        if not title:
            continue
        link = (entry.get("link") or "").strip()
        published = _published(entry)
        summary = _clean(entry.get("summary") or entry.get("description"))[:500]
        items.append({
            "title": title[:500],
            "link": link[:800] or None,
            "published_at": published,
            "summary": summary or None,
            "content_hash": content_hash(title, link),
            "raw": json.dumps({"title": title, "link": link}, ensure_ascii=False)[:2000],
        })
    return items


def upsert_items(session: Session, source: NewsSource, items: list[dict]) -> tuple[int, int]:
    """返回 (新增数, 跳过重复数)。"""
    added = skipped = 0
    for item in items:
        existing = session.execute(
            select(NewsItem).where(NewsItem.content_hash == item["content_hash"])
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        session.add(NewsItem(
            source_id=source.id,
            title=item["title"],
            link=item["link"],
            published_at=item["published_at"],
            summary=item["summary"],
            content_hash=item["content_hash"],
            lang=source.lang,
            raw=item["raw"],
        ))
        added += 1
    session.commit()
    return added, skipped


def run_collect(session: Session, sources: list[NewsSource]) -> dict:
    """对启用的源逐一采集。返回汇总；单源失败不影响其他源。"""
    results = []
    total_added = 0
    for source in sources:
        entry = {"source": source.name, "ok": False, "added": 0, "skipped": 0, "error": None}
        try:
            xml_text = fetch_feed(source.url)
            items = parse_entries(xml_text, source)
            added, skipped = upsert_items(session, source, items[:100])
            entry.update(ok=True, added=added, skipped=skipped, total=len(items))
            total_added += added
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)
    return {
        "ok": all(r["ok"] for r in results),
        "sources_total": len(results),
        "sources_ok": sum(1 for r in results if r["ok"]),
        "sources_failed": [r["source"] for r in results if not r["ok"]],
        "items_added": total_added,
        "details": results,
    }
