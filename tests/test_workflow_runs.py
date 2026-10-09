import pytest
from sqlalchemy import select

from src.domain.db import make_engine, make_session_factory
from src.domain.models import Base, WorkflowRun
from src.workflows.runs import ConflictError, finish_run, start_run


@pytest.fixture()
def session():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        yield s
    engine.dispose()


def test_conflict_when_running(session):
    run = start_run(session, "collect")
    with pytest.raises(ConflictError):
        start_run(session, "collect")
    finish_run(session, run, ok=True, output={"items_added": 3})
    assert session.get(WorkflowRun, run.id).status == "success"


def test_idempotency_key_returns_history(session):
    run1 = start_run(session, "collect", idempotency_key="k1")
    finish_run(session, run1, ok=True, output={"a": 1})
    run2 = start_run(session, "collect", idempotency_key="k1")
    assert run2.id == run1.id and run2.status == "success"
    assert len(session.execute(select(WorkflowRun)).scalars().all()) == 1
