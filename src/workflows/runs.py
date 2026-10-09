"""任务编排基础：唯一 ID、状态、幂等、有限并发。"""
from __future__ import annotations

import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import WorkflowRun, utcnow


class ConflictError(Exception):
    """同一类型任务正在运行，拒绝重复触发。"""


def start_run(
    session: Session,
    run_type: str,
    idempotency_key: str | None = None,
    input_data: dict | None = None,
) -> WorkflowRun:
    if idempotency_key:
        existing = session.execute(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing and existing.status == "running":
            raise ConflictError(f"任务 {idempotency_key} 已在运行中")
        if existing:
            # 已完成过：直接返回历史记录（幂等，不重复执行）
            return existing
    active = session.execute(
        select(WorkflowRun).where(WorkflowRun.run_type == run_type, WorkflowRun.status == "running")
    ).scalar_one_or_none()
    if active:
        raise ConflictError(f"任务类型 {run_type} 正在运行中（run_id={active.id}）")
    run = WorkflowRun(
        run_type=run_type,
        status="running",
        idempotency_key=idempotency_key,
        input_json=json.dumps(input_data or {}, ensure_ascii=False),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def finish_run(session: Session, run: WorkflowRun, ok: bool, output: dict | None = None, error: str | None = None) -> WorkflowRun:
    run.status = "success" if ok else "failed"
    run.output_json = json.dumps(output or {}, ensure_ascii=False)
    run.error = error
    run.finished_at = utcnow()
    session.commit()
    session.refresh(run)
    return run
