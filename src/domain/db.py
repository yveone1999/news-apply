"""数据库引擎与会话管理。"""
from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def resolve_db_url(url: str, project_root: Path | None = None) -> str:
    """把 sqlite:///data/app.db 这类相对路径锚定到项目根目录。"""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///"):]
        root = project_root or Path(__file__).resolve().parents[2]
        path = Path(rel)
        if not path.is_absolute():
            path = root / path
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{path}"
    return url


def make_engine(url: str):
    url = resolve_db_url(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_pragma(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


def make_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
