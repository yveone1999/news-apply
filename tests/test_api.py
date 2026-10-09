def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["db"] == "ok"


def test_list_sources(client):
    resp = client.get("/api/v1/news-sources")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert any(s["name"] == "TestFeed" for s in body["items"])


def test_create_source_and_conflict(client):
    payload = {"name": "NewFeed", "url": "https://example.com/new", "type": "rss"}
    assert client.post("/api/v1/news-sources", json=payload).status_code == 201
    assert client.post("/api/v1/news-sources", json=payload).status_code == 409


def test_patch_source_toggle(client):
    sources = client.get("/api/v1/news-sources").json()["items"]
    target = next(s for s in sources if s["name"] == "TestFeed")
    resp = client.patch(f"/api/v1/news-sources/{target['id']}", json={"enabled": False})
    assert resp.status_code == 200 and resp.json()["enabled"] is False


def test_news_items_filter(client):
    from src.domain.db import make_session_factory
    from src.domain.models import NewsItem

    engine = client.app.state.engine
    with make_session_factory(engine)() as s:
        from src.domain.models import NewsSource
        s.add(NewsSource(name="OtherFeed", url="https://other.com/rss", enabled=True))
        s.commit()
        other_id = s.query(NewsSource).filter_by(name="OtherFeed").first().id
        s.add(NewsItem(title="A", link="https://a", content_hash="h1", source_id=1))
        s.add(NewsItem(title="B", link="https://b", content_hash="h2", source_id=other_id))
        s.commit()
    resp = client.get("/api/v1/news-items")
    assert resp.status_code == 200 and resp.json()["count"] == 2
    resp2 = client.get("/api/v1/news-items", params={"source_id": 1})
    assert resp2.json()["count"] == 1 and resp2.json()["items"][0]["title"] == "A"
