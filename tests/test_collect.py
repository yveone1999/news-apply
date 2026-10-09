import pytest
from sqlalchemy import select

from src.collectors.feeds import content_hash, parse_entries, run_collect, upsert_items
from src.domain.db import make_engine, make_session_factory
from src.domain.models import Base, NewsItem, NewsSource

SAMPLE_RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Alpha ships new model</title><link>https://example.com/1</link>
<pubDate>Fri, 09 Oct 2026 08:00:00 GMT</pubDate><description>Alpha announced a new model today.</description></item>
<item><title>Beta raises funding</title><link>https://example.com/2</link>
<pubDate>Fri, 09 Oct 2026 07:00:00 GMT</pubDate><description>Beta raised money.</description></item>
</channel></rss>"""


@pytest.fixture()
def session():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        s.add(NewsSource(name="TestFeed", url="https://example.com/rss", enabled=True))
        s.commit()
        yield s
    engine.dispose()


def test_parse_entries(session):
    items = parse_entries(SAMPLE_RSS, session.execute(select(NewsSource)).scalar_one())
    assert len(items) == 2
    assert items[0]["title"] == "Alpha ships new model"
    assert items[0]["link"] == "https://example.com/1"
    assert items[0]["published_at"] is not None
    assert items[0]["summary"].startswith("Alpha announced")


def test_content_hash_stable():
    assert content_hash("Hello World", "https://x") == content_hash("hello   world", "https://x")
    assert content_hash("A", "x") != content_hash("B", "x")


def test_upsert_dedup(session):
    source = session.execute(select(NewsSource)).scalar_one()
    items = parse_entries(SAMPLE_RSS, source)
    added, skipped = upsert_items(session, source, items)
    assert (added, skipped) == (2, 0)
    added2, skipped2 = upsert_items(session, source, items)
    assert (added2, skipped2) == (0, 2)


def test_run_collect_partial_failure(monkeypatch, session):
    import src.collectors.feeds as feeds

    def fake_fetch(url, timeout=25.0):
        if "example.com" in url:
            raise ConnectionError("boom")
        return SAMPLE_RSS

    session.add(NewsSource(name="GoodFeed", url="https://good.com/rss", enabled=True))
    session.commit()
    monkeypatch.setattr(feeds, "fetch_feed", fake_fetch)
    sources = session.execute(select(NewsSource)).scalars().all()
    result = run_collect(session, sources)
    assert result["sources_ok"] == 1
    assert result["sources_failed"] == ["TestFeed"]
    detail = next(d for d in result["details"] if d["source"] == "TestFeed")
    assert "boom" in detail["error"]
    assert result["items_added"] == 2
