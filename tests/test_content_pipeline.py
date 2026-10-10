"""阶段 C 单元测试：评分/研究/写作/质量门禁（LLM 用 MockTransport 模拟）。"""
import json

import httpx
import pytest
from sqlalchemy import select

from src.domain.db import make_engine, make_session_factory
from src.domain.models import Base, NewsItem, NewsSource, Topic, utcnow
from src.llm.client import LLMClient, LLMConfig
from src.quality.gates import rule_checks
from src.ranking.scoring import score_topics
from src.research.research import build_research
from src.writing.writer import ArticleConflictError, generate_article

BODY_500 = "这是正文测试内容。" * 60 + "你如何看待这一变化？"


def mock_llm(responses: dict, **cfg):
    def handler(request):
        body = json.loads(request.content)
        user_msg = next(m["content"] for m in body["messages"] if m["role"] == "user")
        for key, resp in responses.items():
            if key in user_msg:
                return httpx.Response(200, json={"choices": [{"message": {"content": resp}}]})
        return httpx.Response(500, json={"error": "no mock for this prompt"})

    return LLMClient(LLMConfig(base_url="http://mock/v1", model="m", max_retries=1),
                     transport=httpx.MockTransport(handler))


@pytest.fixture()
def session():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        src = NewsSource(name="TestFeed", url="https://seed.com/rss", enabled=True)
        s.add(src)
        s.commit()
        for i, link in enumerate(["https://seed.com/1", "https://seed.com/2"], 1):
            s.add(NewsItem(title=f"Alpha news {i}", link=link, content_hash=f"h{i}",
                           source_id=src.id, published_at=utcnow(), summary="summary text"))
        s.commit()
        yield s
    engine.dispose()


def test_score_topics_clamps_and_filters(session):
    topics_json = json.dumps([
        {"title": "一个足够长的测试选题标题", "reason": "r",
         "scores": {"audience": 99, "reliability": 20, "differentiation": 10, "timeliness": 10, "fit": 10},
         "item_ids": [1, 424242], "suggested_column": "玄知深度拆解"},
        {"title": "短", "scores": {}, "item_ids": [1]},
    ], ensure_ascii=False)
    llm = mock_llm({"选题编辑": topics_json})
    items = [{"id": 1, "title": "a", "source": "s", "summary": ""},
             {"id": 2, "title": "b", "source": "s", "summary": ""}]
    results = score_topics(llm, items, max_topics=3)
    assert len(results) == 1
    assert results[0]["scores"]["audience"] == 25.0
    assert results[0]["item_ids"] == [1]
    assert results[0]["suggested_column"] == "玄知深度拆解"


def test_research_invalid_url_cleared(session):
    research_json = json.dumps({
        "content": "研究内容",
        "evidence": [
            {"fact": "事实A", "source_title": "T", "source_url": "https://seed.com/1", "verified": True},
            {"fact": "事实B(虚构链接)", "source_title": "T", "source_url": "https://fake.com/x", "verified": True},
        ],
        "open_questions": ["q1"], "conclusion": "结论",
    }, ensure_ascii=False)
    llm = mock_llm({"研究员": research_json})
    items = [{"id": 1, "title": "t", "link": "https://seed.com/1", "summary": "", "source": "s", "published_at": ""}]
    result = build_research(llm, "测试选题", items)
    ev_a, ev_b = result["evidence"]
    assert ev_a["verified"] is True and ev_a["source_url"] == "https://seed.com/1"
    assert ev_b["verified"] is False and ev_b["source_url"] == ""
    assert result["verified_count"] == 1


def test_writer_idempotent_and_versioned(session):
    topic = Topic(title="测试选题", column_name="全球 AI 前沿速递", item_ids="[]")
    from src.domain.models import ResearchRecord
    s = session
    s.add(topic)
    s.flush()
    research = ResearchRecord(topic_id=topic.id, content="研究档案", evidence="[]", conclusion="结论")
    s.add(research)
    s.commit()

    article_json = json.dumps({"title": "测试文章标题长度足够", "summary": "摘要", "body": BODY_500}, ensure_ascii=False)
    research_json = json.dumps({"content": "x", "evidence": [], "open_questions": [], "conclusion": ""}, ensure_ascii=False)
    llm = mock_llm({"主笔": article_json, "研究员": research_json})

    a1 = generate_article(llm, s, topic, research, change_note="初稿")
    assert a1.current_version == 1 and a1.status == "draft"
    a2 = generate_article(llm, s, topic, research, change_note="修改")
    assert a2.current_version == 2

    from src.domain.models import Article
    a2.status = "approved"
    s.commit()
    with pytest.raises(ArticleConflictError):
        generate_article(llm, s, topic, research)


def test_rule_checks(session):
    from src.domain.models import Article
    a = Article(title="最先进模型发布", body="这段正文" * 50 + "没有结尾问题。")
    session.add(a)
    session.commit()
    issues = rule_checks(a, session)
    assert any("最先进" in i for i in issues)
    assert any("标题长度" in i for i in issues)
    assert any("互动问题" in i for i in issues)


def test_quality_gate_hard_block_no_evidence(session):
    from src.domain.models import Article, ResearchRecord, Topic
    topic = Topic(title="t", column_name="全球 AI 前沿速递", item_ids="[]")
    session.add(topic)
    session.flush()
    research = ResearchRecord(topic_id=topic.id, content="无证据", evidence="[]", conclusion="")
    article = Article(topic_id=topic.id, title="正常长度标题足够长", body=BODY_500, column_name="全球 AI 前沿速递")
    session.add_all([research, article])
    session.commit()

    quality_json = json.dumps({"facts": [], "unsupported": [], "unmarked_uncertainty": [], "logic": [], "comment": "ok"}, ensure_ascii=False)
    llm = mock_llm({"审核员": quality_json})
    from src.quality.gates import run_quality_gate
    report = run_quality_gate(llm, session, article, research)
    assert report["passed"] is False
    assert any("硬门禁" in i for i in report["issues"])
