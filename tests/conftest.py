import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.domain.db import make_engine, make_session_factory  # noqa: E402
from src.domain.models import Base, NewsSource  # noqa: E402
import apps.api.main as main_module  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test.db"
    engine = make_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    main_module.app.state.engine = engine
    main_module.SessionLocal = session_factory
    with session_factory() as s:
        s.add(NewsSource(name="TestFeed", url="https://example.com/rss", enabled=True))
        s.commit()
    with TestClient(main_module.app) as c:
        yield c
    engine.dispose()
