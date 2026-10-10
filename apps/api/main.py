"""FastAPI 业务 API（阶段 B：资讯源 / 采集 / 资讯条目 / 任务 / 模型测试 / 健康检查）。"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.collectors.feeds import run_collect
from src.domain.db import make_engine, make_session_factory
from src.domain.models import Base, NewsItem, NewsSource, WorkflowRun, utcnow
from src.llm.client import LLMClient, LLMConfig, LLMError
from src.observability.logging import setup_logging
from src.workflows.runs import ConflictError, finish_run, start_run
from apps.api.routes_content import build_routes
from apps.api.routes_ops import build_routes as build_ops_routes

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from dotenv import dotenv_values  # noqa: E402

_env_values = dotenv_values(PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return _env_values.get(key, default) or default


def build_llm_config() -> LLMConfig:
    return LLMConfig(
        base_url=_env("LLM_BASE_URL"),
        api_key=_env("LLM_API_KEY"),
        model=_env("LLM_MODEL", "DeepSeek-V4-Flash"),
        timeout_seconds=float(_env("LLM_TIMEOUT_SECONDS", "120")),
        max_retries=int(_env("LLM_MAX_RETRIES", "3")),
    )


def get_llm() -> LLMClient:
    return LLMClient(build_llm_config())


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = app.state.engine
    Base.metadata.create_all(engine)  # 兜底建表；结构演进由 alembic 管理
    session = SessionLocal()
    try:
        if not session.execute(select(NewsSource).limit(1)).scalars().first():
            config_path = PROJECT_ROOT / "configs" / "news_sources.yaml"
            if config_path.exists():
                cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                for item in cfg.get("sources", []):
                    session.add(NewsSource(
                        name=item["name"], url=item["url"],
                        source_type=item.get("type", "rss"), lang=item.get("lang", "en"),
                        enabled=bool(item.get("enabled", True)), note=item.get("note"),
                    ))
                session.commit()
    finally:
        session.close()
    yield


app = FastAPI(title="玄知见解 · 内容运营系统", version="0.1.0", lifespan=lifespan)
app.state.engine = make_engine(_env("DB_URL", "sqlite:///data/app.db"))
SessionLocal = make_session_factory(app.state.engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.include_router(build_routes(get_db, get_llm))  # 阶段 C 内容路由
app.include_router(build_ops_routes(get_db))  # 阶段 D 运营路由


# ---------- 健康检查 ----------

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "db": "ok", "service": "xuan-zhi-content-engine"}


# ---------- 资讯源 ----------

class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=5, max_length=500)
    type: str = "rss"
    lang: str = "en"
    enabled: bool = True
    note: str | None = None


class SourcePatch(BaseModel):
    enabled: bool | None = None
    note: str | None = None
    url: str | None = None


@app.get("/api/v1/news-sources")
def list_sources(db: Session = Depends(get_db)):
    rows = db.execute(select(NewsSource).order_by(NewsSource.name)).scalars().all()
    return {"count": len(rows), "items": [
        {"id": s.id, "name": s.name, "url": s.url, "type": s.source_type,
         "lang": s.lang, "enabled": s.enabled, "note": s.note} for s in rows
    ]}


@app.post("/api/v1/news-sources", status_code=201)
def create_source(body: SourceIn, db: Session = Depends(get_db)):
    if db.execute(select(NewsSource).where(NewsSource.name == body.name)).scalar_one_or_none():
        raise HTTPException(409, f"来源 {body.name} 已存在")
    source = NewsSource(name=body.name, url=body.url, source_type=body.type,
                      lang=body.lang, enabled=body.enabled, note=body.note)
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"id": source.id, "name": source.name}


@app.patch("/api/v1/news-sources/{source_id}")
def patch_source(source_id: int, body: SourcePatch, db: Session = Depends(get_db)):
    source = db.get(NewsSource, source_id)
    if not source:
        raise HTTPException(404, "来源不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    db.commit()
    return {"id": source.id, "name": source.name, "enabled": source.enabled}


# ---------- 采集 ----------

@app.post("/api/v1/collect/run")
def collect_run(db: Session = Depends(get_db)):
    sources = db.execute(
        select(NewsSource).where(NewsSource.enabled.is_(True)).order_by(NewsSource.name)
    ).scalars().all()
    if not sources:
        raise HTTPException(400, "没有启用的资讯源")
    today = utcnow().strftime("%Y-%m-%d")
    try:
        run = start_run(db, run_type="collect", idempotency_key=f"collect:{today}:{'|'.join(s.name for s in sources)}")
    except ConflictError as exc:
        raise HTTPException(409, str(exc))
    if run.status != "running":
        return {"run_id": run.id, "note": "今日采集已完成（幂等返回历史记录）", "output": json.loads(run.output_json or "{}")}
    try:
        result = run_collect(db, sources)
        finish_run(db, run, ok=True, output=result)
        return {"run_id": run.id, **result}
    except Exception as exc:  # noqa: BLE001
        finish_run(db, run, ok=False, error=f"{type(exc).__name__}: {exc}")
        raise HTTPException(502, f"采集失败: {type(exc).__name__}") from exc


@app.get("/api/v1/news-items")
def list_items(
    source_id: int | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = select(NewsItem).order_by(NewsItem.published_at.desc().nullslast(), NewsItem.id.desc())
    if source_id is not None:
        query = query.where(NewsItem.source_id == source_id)
    rows = db.execute(query.limit(limit).offset(offset)).scalars().all()
    return {"count": len(rows), "items": [
        {"id": it.id, "source_id": it.source_id, "title": it.title, "link": it.link,
         "published_at": it.published_at.isoformat() if it.published_at else None,
         "summary": (it.summary or "")[:200], "created_at": it.created_at.isoformat()}
        for it in rows
    ]}


# ---------- 任务 ----------

@app.get("/api/v1/workflow-runs")
def list_runs(run_type: str | None = None, limit: int = Query(default=20, le=100), db: Session = Depends(get_db)):
    query = select(WorkflowRun).order_by(WorkflowRun.started_at.desc())
    if run_type:
        query = query.where(WorkflowRun.run_type == run_type)
    rows = db.execute(query.limit(limit)).scalars().all()
    return {"count": len(rows), "items": [
        {"id": r.id, "run_type": r.run_type, "status": r.status, "error": r.error,
         "started_at": r.started_at.isoformat(), "finished_at": r.finished_at.isoformat() if r.finished_at else None}
        for r in rows
    ]}


# ---------- 模型连接测试 ----------

@app.post("/api/v1/llm/test")
def llm_test():
    client = get_llm()
    try:
        return client.ping()
    except LLMError as exc:
        raise HTTPException(502, f"模型接口不可用: {exc}") from exc
    finally:
        client.close()

# ---------- 静态资源与前端管理台 ----------

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_IMAGES_DIR = PROJECT_ROOT / "storage" / "images"
_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media-files", StaticFiles(directory=str(_IMAGES_DIR)), name="media-files")

_WEB_DIST = PROJECT_ROOT / "apps" / "web" / "dist"
if _WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_WEB_DIST / "assets"), check_dir=False),
              name="web-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404)
        candidate = _WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_WEB_DIST / "index.html")
