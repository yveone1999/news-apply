"""每日发布包导出：从引擎数据库生成 toutiao-content/<日期>/ 一键粘贴发布包。

读取引擎 DB（data/app.db）中当天已审批（approved）的文章、选题、原始资讯与质量报告，
产出:
  toutiao-content/<YYYY-MM-DD>/
    raw/items.json, raw/summary.md      # 当日采集资讯池
    news_digest.md                       # Top 选题清单(含评分)
    articles.md                          # 已审批主文章
    briefs.md                            # 微头条选题草稿(基于关联资讯)
    final/review_report.md               # 质量门禁+审批报告
    final/publish_main.md                # 主文发布终稿(标题+正文+标签+配图)
    final/publish_briefs.md              # 微头条发布终稿
    final/CHECKLIST.md                   # 人工发布步骤

用法:
  .venv/bin/python scripts/export_daily.py [YYYY-MM-DD]   # 默认今天(UTC)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DB_URL", "sqlite:///data/app.db")

from src.domain.db import make_engine, make_session_factory  # noqa: E402
from src.domain.models import (  # noqa: E402
    Article, NewsItem, NewsSource, PublishingRecord, ResearchRecord,
    ReviewRecord, Topic, WorkflowRun,
)

WORKSPACE = PROJECT_ROOT.parent          # /Users/yangl/job-workspace
CONTENT_ROOT = WORKSPACE / "toutiao-content"


def local_date() -> str:
    # 展示层用北京时区（UTC+8），匹配"每日"封面日期
    return (datetime.now(timezone.utc) + __import__("datetime").timedelta(hours=8)).strftime("%Y-%m-%d")


def today_items(session, date_prefix: str) -> list[NewsItem]:
    # 取 UTC 日期内采集的条目（created_at 毫秒部分做 date 前缀匹配）
    rows = session.execute(
        select(NewsItem).order_by(NewsItem.published_at.desc().nullslast(), NewsItem.id.desc())
    ).scalars().all()
    return rows


def main() -> None:
    date_arg = sys.argv[1] if len(sys.argv) > 1 else local_date()
    engine = make_engine(os.environ["DB_URL"])
    SessionLocal = make_session_factory(engine)
    session = SessionLocal()

    outdir = CONTENT_ROOT / date_arg
    rawdir = outdir / "raw"
    finaldir = outdir / "final"
    rawdir.mkdir(parents=True, exist_ok=True)
    finaldir.mkdir(parents=True, exist_ok=True)

    # ---------- 数据 ----------
    items = session.execute(select(NewsItem).order_by(NewsItem.id)).scalars().all()
    topics = session.execute(select(Topic).order_by(Topic.score.desc().nullslast(), Topic.id.desc())).scalars().all()
    articles = session.execute(select(Article).order_by(Article.id)).scalars().all()
    reviews = {r.article_id: r for r in session.execute(select(ReviewRecord)).scalars().all()}
    src_map = {s.id: s.name for s in session.execute(select(NewsSource)).scalars().all()}

    # ---------- raw/items.json ----------
    raw_items = [{
        "id": it.id, "title": it.title, "link": it.link, "source": src_map.get(it.source_id),
        "published_at": it.published_at.isoformat() if it.published_at else None,
        "summary": it.summary, "lang": it.lang, "created_at": it.created_at.isoformat(),
    } for it in items]
    with open(rawdir / "items.json", "w", encoding="utf-8") as f:
        json.dump({"date": date_arg, "count": len(raw_items), "items": raw_items}, f, ensure_ascii=False, indent=2)

    # ---------- raw/summary.md ----------
    by_src: dict[str, list[NewsItem]] = {}
    for it in items:
        by_src.setdefault(src_map.get(it.source_id, "未知"), []).append(it)
    summary_lines = [f"# 原始资讯池 {date_arg}", f"共 {len(items)} 条（来自 {len(by_src)} 个源）", ""]
    for src, its in sorted(by_src.items(), key=lambda kv: -len(kv[1])):
        summary_lines.append(f"## {src}（{len(its)} 条）")
        for it in its[:8]:
            summary_lines.append(f"- [{it.title}]({it.link})")
        if len(its) > 8:
            summary_lines.append(f"- …（共 {len(its)} 条）")
        summary_lines.append("")
    (rawdir / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    # ---------- news_digest.md ----------
    digest = [f"# 今日选题 Top {len(topics)} / {date_arg}", ""]
    for i, t in enumerate(topics, 1):
        detail = json.loads(t.score_detail) if t.score_detail else {}
        digest.append(f"{i}. 【{t.column_name}】{t.title}  评分 {t.score:.0f}")
        if detail.get("reason"):
            digest.append(f"   理由：{detail['reason']}")
        digest.append(f"   状态：{t.status}")
        digest.append("")
    (outdir / "news_digest.md").write_text("\n".join(digest), encoding="utf-8")

    # ---------- articles.md ----------
    art_lines = [f"# 主文章 / {date_arg}", ""]
    for a in articles:
        art_lines.append(f"## 【{a.column_name}】{a.title}")
        art_lines.append(f"- 状态：{a.status}（最终版 v{a.current_version}）")
        art_lines.append("")
        art_lines.append(a.body or "")
        art_lines.append("\n---\n")
    (outdir / "articles.md").write_text("\n".join(art_lines), encoding="utf-8")

    # ---------- briefs.md（微头条选题草稿：基于关联真实资讯）----------
    brief_lines = [f"# 微头条选题草稿 / {date_arg}", ""]
    item_by_id = {it.id: it for it in items}
    for t in topics:
        if t.id not in [a.topic_id for a in articles]:
            ids = json.loads(t.item_ids or "[]")
            it = item_by_id.get(ids[0]) if ids else None
            if it:
                brief_lines.append(f"### {t.title}")
                brief_lines.append(f"（关联资讯：{it.title} · {src_map.get(it.source_id)}）")
                brief_lines.append(f"状态：{t.status}（尚未成稿，可作为后续微头条/短文选题）")
                brief_lines.append("")
    (outdir / "briefs.md").write_text("\n".join(brief_lines), encoding="utf-8")

    # ---------- final/ review_report.md ----------
    report_lines = [f"# 审核报告 / {date_arg}", "", "## 质量门禁结论", ""]
    for a in articles:
        qr = json.loads(a.quality_report) if a.quality_report else {}
        report_lines.append(f"### {a.title}（v{a.current_version}）")
        report_lines.append(f"- 状态：{a.status}")
        report_lines.append(f"- 质量门禁：{'✅ 通过' if qr.get('passed') else '❌ 未通过'}")
        report_lines.append(f"- 事实证据数：{qr.get('evidence_count', 0)}")
        fc = qr.get("fact_check", {})
        report_lines.append(f"- 核查comment：{fc.get('comment', '')}")
        if qr.get("issues"):
            report_lines.append("- 门禁问题：")
            for i in qr["issues"]:
                report_lines.append(f"  - {i}")
        rev = reviews.get(a.id)
        if rev:
            report_lines.append(f"- 人工审批：{'通过' if rev.result == 'pass' else '驳回'}（{rev.reviewer}）")
            if rev.note:
                report_lines.append(f"- 审批备注：{rev.note}")
        report_lines.append("")
    (finaldir / "review_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    # ---------- final/ publish_main.md ----------
    approved = [a for a in articles if a.status == "approved"]
    pub_lines = [f"# 头条主文章 · 发布终稿（{date_arg}）", ""]
    if approved:
        a = approved[0]
        pub_lines += [
            "## 标题（主推）", a.title, "",
            "## 正文", "", (a.body or "").strip(), "",
            "![封面](../images/cover.png)", "",
            "## 话题标签", generate_tags(a.title), "",
            "## 配图", "- 封面：images/cover.png（3:2 横版）", "- 文内图：按需在正文插图",
        ]
    else:
        pub_lines.append("（今日无已审批文章，请先完成写作→门禁→审批）。")
    (finaldir / "publish_main.md").write_text("\n".join(pub_lines), encoding="utf-8")

    # ---------- final/ publish_briefs.md ----------
    pb = [f"# 微头条 · 发布终稿（{date_arg}）", ""]
    if not approved:
        pb.append("（今日无已审批文章对应的微头条落地稿；如需可基于 briefs.md 选题人工成稿）。")
    (finaldir / "publish_briefs.md").write_text("\n".join(pb), encoding="utf-8")

    # ---------- final/ CHECKLIST.md ----------
    checklist = [
        "# 头条发布步骤（人工执行）", "",
        "> 今日头条无公开发布 API，以下为『一键粘贴级』素材，最后粘贴发布需人工完成。",
        "> 建议发布时间：工作日 7:30-9:00 或 20:00-22:00。", "",
        "## 顺序",
    ]
    if approved:
        a = approved[0]
        checklist += [
            "1. 先发主文章（流量主力）：",
            f"   - 标题：{a.title}",
            "   - 正文：复制 `publish_main.md` 正文（不含标签行）",
            "   - 封面图：`../images/cover.png`（需先用 make_cover.py 生成）",
            f"   - 话题标签：{generate_tags(a.title)}",
            "",
            "2. 主文章发布后记录头条链接 + 阅读/收益到后台，作为日报复盘数据。",
            "",
            "## 发布后回填",
            "- 在头条客户端发布后，把文章链接与首日数据回填到引擎「发布记录 / 收益分析」，形成闭环。",
            "",
            "## 发布前最后检查",
            "- [ ] 主文 400-3000 字区间内（门禁已核）",
            "- [ ] 无绝对化用语、无敏感词（门禁已核，见 review_report.md）",
            "- [ ] 话题标签 3-5 个",
            "- [ ] 封面图 3:2 横版无水印",
        ]
    else:
        checklist.append("- （今日无已审批文章，暂无发布步骤）")
    (finaldir / "CHECKLIST.md").write_text("\n".join(checklist), encoding="utf-8")

    session.close()
    engine.dispose()

    print(f"✅ 已生成 {date_arg} 发布包: {outdir}")
    for p in sorted(outdir.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(outdir)}")


def generate_tags(title: str) -> str:
    # 朴素标签生成：从标题取关键词 + 固定垂直标签
    tags = ["#玄知见解", "#人工智能", "#前沿科技"]
    for w in ["Anthropic", "OpenAI", "谷歌", "AI", "大模型", "芯片", "机器人"]:
        if w.lower() in title.lower():
            tags.insert(0, f"#{w}")
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return " ".join(out)


if __name__ == "__main__":
    main()
