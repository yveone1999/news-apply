"""阶段 D 测试：编辑/版本恢复/发布/收益/素材/备份/看板/分析。"""
import io

import pytest
from fastapi.testclient import TestClient

from src.domain.db import make_engine, make_session_factory
from src.domain.models import Article, ArticleVersion, Base, Topic
import apps.api.main as main_module


@pytest.fixture()
def client(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'ops.db'}")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    main_module.app.state.engine = engine
    main_module.SessionLocal = factory

    def override_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    with TestClient(main_module.app) as c:
        yield c, factory
    main_module.app.dependency_overrides.clear()
    engine.dispose()


import uuid


def seed_article(factory, status="draft"):
    with factory() as s:
        topic = Topic(title=f"测试选题标题-{uuid.uuid4().hex[:8]}", column_name="全球 AI 前沿速递", item_ids="[]")
        s.add(topic)
        s.flush()
        article = Article(topic_id=topic.id, title="初始标题长度足够", body="正文内容" * 30,
                          column_name="全球 AI 前沿速递", status=status)
        s.add(article)
        s.flush()
        s.add(ArticleVersion(article_id=article.id, version=1, title=article.title, body=article.body))
        s.commit()
        return article.id, topic.id


def test_edit_creates_version_and_invalidates_quality(client):
    c, factory = client
    aid, _ = seed_article(factory)
    r = c.put(f"/api/v1/articles/{aid}", json={"body": "新正文" * 20, "change_note": "改"})
    assert r.status_code == 200 and r.json()["current_version"] == 2
    # approved 状态不可编辑
    aid2, _ = seed_article(factory, status="approved")
    assert c.put(f"/api/v1/articles/{aid2}", json={"body": "x"}).status_code == 409


def test_version_restore(client):
    c, factory = client
    aid, _ = seed_article(factory)
    c.put(f"/api/v1/articles/{aid}", json={"body": "改过的正文" * 20})
    r = c.post(f"/api/v1/articles/{aid}/versions/1/restore")
    assert r.status_code == 200 and r.json()["current_version"] == 3
    detail = c.get(f"/api/v1/articles/{aid}").json()
    assert detail["body"] == "正文内容" * 30


def test_publish_requires_approved(client):
    c, factory = client
    aid_draft, _ = seed_article(factory, status="draft")
    assert c.post(f"/api/v1/articles/{aid_draft}/publish",
                  json={"url": "https://toutiao.com/a/1"}).status_code == 409
    aid_ok, _ = seed_article(factory, status="approved")
    r = c.post(f"/api/v1/articles/{aid_ok}/publish",
               json={"url": "https://toutiao.com/a/2", "platform": "toutiao"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    pub = c.get("/api/v1/publishing").json()
    assert pub["count"] == 1 and pub["items"][0]["url"] == "https://toutiao.com/a/2"


def test_metrics_upsert(client):
    c, factory = client
    aid, _ = seed_article(factory)
    payload = {"stat_date": "2026-10-10", "reads": 100, "likes": 5, "revenue": 1.5}
    assert c.post(f"/api/v1/articles/{aid}/metrics", json=payload).status_code == 200
    payload2 = {"stat_date": "2026-10-10", "reads": 120}
    assert c.post(f"/api/v1/articles/{aid}/metrics", json=payload2).status_code == 200
    items = c.get(f"/api/v1/articles/{aid}/metrics").json()["items"]
    assert len(items) == 1 and items[0]["reads"] == 120 and items[0]["likes"] == 5  # 未传字段保留


def test_media_upload_requires_provenance(client):
    c, factory = client
    files = {"file": ("a.png", io.BytesIO(b"\x89PNG fake"), "image/png")}
    r = c.post("/api/v1/media", files=files, data={})
    assert r.status_code == 400  # 无来源/授权
    r = c.post("/api/v1/media", files=files, data={"license_note": "自行生成（Pillow）", "usage": "cover"})
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert c.get("/api/v1/media").json()["count"] == 1
    assert c.delete(f"/api/v1/media/{mid}").json()["deleted"] == mid
    assert c.get("/api/v1/media").json()["count"] == 0


def test_backup_and_settings(client, tmp_path):
    c, factory = client
    seed_article(factory)
    b = c.post("/api/v1/backup/run")
    assert b.status_code == 200 and b.json()["name"].startswith("app-")
    lst = c.get("/api/v1/backup/list").json()
    assert lst["count"] >= 1
    r = c.put("/api/v1/settings", json={"key": "account.name", "value": "玄知见解"})
    assert r.status_code == 200
    assert c.get("/api/v1/settings").json()["items"][0]["key"] == "account.name"


def test_dashboard_and_analytics(client):
    c, factory = client
    aid, _ = seed_article(factory, status="published")
    c.post(f"/api/v1/articles/{aid}/metrics",
           json={"stat_date": "2026-10-09", "reads": 500, "likes": 10, "revenue": 3.2})
    ov = c.get("/api/v1/dashboard/overview").json()
    assert ov["published_total"] == 1 and ov["reads_total"] == 500
    assert ov["revenue_total"] == 3.2
    cols = c.get("/api/v1/analytics/columns").json()["columns"]
    assert cols["全球 AI 前沿速递"]["reads"] == 500
    trend = c.get("/api/v1/analytics/trend", params={"days": 7}).json()
    assert any(p["stat_date"] == "2026-10-09" for p in trend["series"])
