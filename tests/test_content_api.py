"""阶段 C 全链路 API 测试：选题→研究→写作→门禁→提交→审批（mock LLM）。"""
import json

import httpx
from fastapi.testclient import TestClient

BODY = "这是正文测试内容，信息密度足够。" * 40 + "你如何看待这一变化？"

TOPICS_JSON = json.dumps([
    {"title": "OpenAI 发布新模型引发行业震动", "reason": "多方报道",
     "scores": {"audience": 20, "reliability": 20, "differentiation": 12, "timeliness": 12, "fit": 12},
     "item_ids": [1, 2], "suggested_column": "全球 AI 前沿速递"},
], ensure_ascii=False)
RESEARCH_JSON = json.dumps({
    "content": "研究档案内容",
    "evidence": [{"fact": "OpenAI 发布新模型", "source_title": "TestFeed", "source_url": "https://seed.com/1", "verified": True}],
    "open_questions": ["细节待核"], "conclusion": "事件属实（单源）",
}, ensure_ascii=False)
ARTICLE_JSON = json.dumps({"title": "OpenAI 新模型发布：行业震动", "summary": "摘要", "body": BODY}, ensure_ascii=False)
QUALITY_OK = json.dumps({"facts": [{"fact": "发布新模型", "in_evidence": True}], "unsupported": [],
                         "unmarked_uncertainty": [], "logic": [], "comment": "通过"}, ensure_ascii=False)
QUALITY_BAD = json.dumps({"facts": [], "unsupported": ["正文出现无依据数字 500 亿"],
                          "unmarked_uncertainty": [], "logic": [], "comment": "存在无依据陈述"}, ensure_ascii=False)


def make_handler(quality: str = QUALITY_OK):
    def handler(request):
        body = json.loads(request.content)
        user_msg = next(m["content"] for m in body["messages"] if m["role"] == "user")
        for key, resp in (("选题编辑", TOPICS_JSON), ("研究员", RESEARCH_JSON),
                          ("主笔", ARTICLE_JSON), ("审核员", quality)):
            if key in user_msg:
                return httpx.Response(200, json={"choices": [{"message": {"content": resp}}]})
        return httpx.Response(500, json={"error": "unhandled prompt"})
    return handler


def build_client(quality: str = QUALITY_OK):
    import pytest
    from pathlib import Path
    import tempfile
    from src.domain.db import make_engine, make_session_factory
    from src.domain.models import Base, NewsItem, NewsSource, utcnow
    from src.llm.client import LLMClient, LLMConfig
    import apps.api.main as main_module

    tmp = Path(tempfile.mkdtemp())
    engine = make_engine(f"sqlite:///{tmp / 't.db'}")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    main_module.app.state.engine = engine
    main_module.SessionLocal = factory
    with factory() as s:
        src = NewsSource(name="TestFeed", url="https://seed.com/rss", enabled=True)
        s.add(src)
        s.commit()
        for i, link in enumerate(["https://seed.com/1", "https://seed.com/2"], 1):
            s.add(NewsItem(title=f"Alpha news {i}", link=link, content_hash=f"hh{i}",
                           source_id=src.id, published_at=utcnow(), summary="s"))
        s.commit()

    mock = LLMClient(LLMConfig(base_url="http://mock/v1", model="m", max_retries=1),
                     transport=httpx.MockTransport(make_handler(quality)))

    def override_llm():
        return mock

    def override_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    main_module.app.dependency_overrides[main_module.get_llm] = override_llm
    with TestClient(main_module.app) as c:
        yield c
    main_module.app.dependency_overrides.clear()
    engine.dispose()


def test_full_pipeline(client_factory=None):
    from tests.test_content_api import build_client
    gen = build_client()
    c = next(gen)
    try:
        # 1 选题生成
        r = c.post("/api/v1/topics/generate", json={"max_topics": 3, "hours": 24})
        assert r.status_code == 200, r.text
        topics = r.json()["topics"]
        assert len(topics) == 1 and topics[0]["score"] == 76.0
        topic_id = r.json()["topics"][0]["score"] and c.get("/api/v1/topics").json()["items"][0]["id"]

        # 2 研究
        r = c.post(f"/api/v1/topics/{topic_id}/research")
        assert r.status_code == 200, r.text
        assert r.json()["verified_count"] == 1

        # 3 写作
        r = c.post("/api/v1/articles/generate", json={"topic_id": topic_id})
        assert r.status_code == 200, r.text
        article_id = r.json()["article_id"]
        assert r.json()["version"] == 1

        # 4 质量门禁（通过）
        r = c.post(f"/api/v1/articles/{article_id}/quality-check")
        assert r.status_code == 200, r.text
        assert r.json()["passed"] is True

        # 5 提交审核 + 批准
        assert c.post(f"/api/v1/articles/{article_id}/submit").json()["status"] == "in_review"
        assert c.post(f"/api/v1/articles/{article_id}/approve", json={"reviewer": "测试"}).json()["status"] == "approved"

        # 6 已批准文章不可重复生成覆盖
        r = c.post("/api/v1/articles/generate", json={"topic_id": topic_id})
        assert r.status_code == 409
    finally:
        try:
            gen.close()
        except Exception:
            pass


def test_quality_failure_blocks_submit():
    from tests.test_content_api import build_client
    gen = build_client(quality=QUALITY_BAD)
    c = next(gen)
    try:
        topic_id = c.get("/api/v1/topics").json()  # 还没有选题
        r = c.post("/api/v1/topics/generate", json={"max_topics": 2})
        topic_id = c.get("/api/v1/topics").json()["items"][0]["id"]
        assert c.post(f"/api/v1/topics/{topic_id}/research").status_code == 200
        article_id = c.post("/api/v1/articles/generate", json={"topic_id": topic_id}).json()["article_id"]
        q = c.post(f"/api/v1/articles/{article_id}/quality-check")
        assert q.json()["passed"] is False
        r = c.post(f"/api/v1/articles/{article_id}/submit")
        assert r.status_code == 409  # 门禁未通过不可提交
    finally:
        try:
            gen.close()
        except Exception:
            pass
