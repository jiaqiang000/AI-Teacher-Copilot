"""Submission 业务 API:提交 / 查询 / SSE 事件 / 批改结果(按 contracts/grading-api.md)。

MVP 认证身份占位:Header X-Student-Id(实现阶段接 DeerFlow Runtime Context)。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import GradingResult, OcrResult
from app.teacher_copilot.db.models.homework import Question
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.grading.stream_adapter import publish_grading_event
from app.teacher_copilot.grading.workflow import schedule_grading
from app.teacher_copilot.services.submission_service import SubmissionService

router = APIRouter(prefix="/api/teacher-copilot/submissions")


@router.post("/")
async def submit(
    body: dict,
    x_student_id: str = Header(default="stu_001"),
):
    """学生提交答案图片(立即返回,后台异步批改)。

    body: {question_id, homework_id, image_url}
    """
    try:
        async with SubmissionService() as svc:
            sub, created = await svc.submit(
                student_id=x_student_id,
                question_id=body["question_id"],
                homework_id=body["homework_id"],
                image_url=body["image_url"],
            )
        await publish_grading_event(
            "grading.stage.started", submission_id=sub.submission_id, stage="QUEUED",
            label="正在排队批改",
        )
        # 轻量后台异步执行(不引入任务队列,FR-010)
        schedule_grading(sub.submission_id)
        return ok({
            "submission_id": sub.submission_id,
            "status": sub.status,
            "current_stage": sub.current_stage,
            "created": created,
        })
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/{submission_id}")
async def get_submission(submission_id: str):
    """查询当前提交(页面刷新恢复的事实源)。"""
    try:
        async with SubmissionService() as svc:
            sub = await svc.get(submission_id)
        return ok({
            "submission_id": sub.submission_id,
            "status": sub.status,
            "current_stage": sub.current_stage,
            "error_code": sub.error_code,
            "error_message": sub.error_message,
            "image_url": sub.image_url,
        })
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/{submission_id}/events")
async def events(submission_id: str, request: Request):
    """SSE 实时批改进度事件(复用 DeerFlow StreamBridge)。"""
    try:
        async with SubmissionService() as svc:
            await svc.get(submission_id)
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))

    from app.gateway.app import app as gw_app

    bridge = getattr(gw_app.state, "stream_bridge", None)
    if bridge is None:
        raise HTTPException(503, detail=dict(code="STREAM_BRIDGE_UNAVAILABLE", message="流式桥未就绪"))
    from app.teacher_copilot.grading.stream_adapter import subscribe_sse

    return subscribe_sse(bridge, submission_id, request)


@router.get("/{submission_id}/grading-result")
async def grading_result(submission_id: str):
    """读取当前有效 GradingResult(SUCCEEDED 后返回,否则 404 语义)。"""
    async with get_session() as session:
        row = await session.scalar(
            select(GradingResult).where(GradingResult.submission_id == submission_id)
        )
    if row is None:
        raise HTTPException(404, detail=dict(code="GRADING_RESULT_NOT_FOUND", message="批改结果尚未生成"))
    return ok({
        "grading_result_id": row.grading_result_id,
        "submission_id": row.submission_id,
        "subject": row.subject,
        "question_type": row.question_type,
        "difficulty": row.difficulty,
        "score": {"earned": row.score_earned, "max": row.score_max, "rate": row.score_rate},
        "feedback": row.feedback,
        "diagnosis": await _load_diagnosis(row.grading_result_id),
        "math_detail": row.math_detail,
        "english_essay_detail": row.english_essay_detail,
        "execution_meta": row.execution_meta,
    })


async def _load_diagnosis(grading_result_id: str) -> dict:
    """组装 diagnosis(知识点 + 错误,含标准 name/type 与 raw 语义)。"""
    from app.teacher_copilot.db.models.grading import (
        GradingResultError,
        GradingResultKnowledgePoint,
    )

    async with get_session() as session:
        kps = await session.scalars(
            select(GradingResultKnowledgePoint).where(
                GradingResultKnowledgePoint.grading_result_id == grading_result_id
            )
        )
        errs = await session.scalars(
            select(GradingResultError).where(
                GradingResultError.grading_result_id == grading_result_id
            )
        )
        return {
            "knowledge_points": [
                {"key": k.knowledge_point_key, "name": k.name, "raw_name": k.raw_name,
                 "performance": k.performance, "evidence": k.evidence}
                for k in kps
            ],
            "errors": [
                {"code": e.error_code, "type": e.type_name, "raw_type": e.raw_type,
                 "knowledge_point_key": e.knowledge_point_key,
                 "description": e.description, "evidence": e.evidence}
                for e in errs
            ],
        }


async def _load_ocr_layout(submission_id: str) -> list:
    """读取 OCR 布局(数学错误定位用)。"""
    async with get_session() as session:
        row = await session.scalar(select(OcrResult).where(OcrResult.submission_id == submission_id))
    return (row.layout_details or []) if row else []
