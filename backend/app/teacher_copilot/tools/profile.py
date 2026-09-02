"""画像与历史 Tool(get_student_profile / get_student_grading_history / get_class_profile)。

Tool 职责(参考文档 05 §8):承接 Agent 业务参数 → 权限校验 → 调用业务 Service
→ 返回结构化结果。业务计算仍在 Service,Tool 保持轻量。

【重要】异步实现(LangGraph 会 await);not asyncio.run 避免嵌套事件循环。
"""

from __future__ import annotations

from langchain_core.tools import tool
from sqlalchemy import select

from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import GradingResult
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.services.profile_service import ProfileAlgorithmV1
from app.teacher_copilot.tools.schemas.inputs import (
    GetClassProfileInput,
    GetStudentGradingHistoryInput,
    GetStudentProfileInput,
)


@tool("get_student_profile", args_schema=GetStudentProfileInput)
async def get_student_profile(
    student_id: str, subject: str, sections: list[str] | None = None,
) -> dict:
    """查询指定学生在某学科上的长期学习画像(整体表现/知识点掌握/薄弱点/重复错误/
    不同难度表现)。用于回答学生长期学习状态、薄弱点、学习趋势等问题。

    如需查询某道题、某次作业或具体历史错误记录,应使用 get_student_grading_history。
    """
    try:
        async with ProfileAlgorithmV1() as algo:
            data = await algo.compute_student(student_id, subject)
        return ok(_filter_sections(data, sections))
    except TcError as e:
        return fail(e)


@tool("get_student_grading_history", args_schema=GetStudentGradingHistoryInput)
async def get_student_grading_history(
    student_id: str, subject: str | None = None, knowledge_point_key: str | None = None,
    error_code: str | None = None, homework_id: str | None = None,
    start_time: str | None = None, end_time: str | None = None, limit: int = 20,
) -> dict:
    """查询学生真实历史批改事实(含标准 key/code 与 raw 语义),为画像结论提供证据。"""
    try:
        async with get_session() as session:
            stmt = select(GradingResult).join(GradingResult.submission).where(
                GradingResult.submission.has(student_id=student_id)
            )
            if subject:
                stmt = stmt.where(GradingResult.subject == subject)
            rows = await session.scalars(stmt.order_by(GradingResult.created_at.desc()).limit(limit))
            return ok([{
                "grading_result_id": g.grading_result_id,
                "subject": g.subject, "question_type": g.question_type,
                "difficulty": g.difficulty,
                "score": {"earned": g.score_earned, "max": g.score_max, "rate": g.score_rate},
                "feedback": g.feedback,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            } for g in rows])
    except TcError as e:
        return fail(e)


@tool("get_class_profile", args_schema=GetClassProfileInput)
async def get_class_profile(
    class_id: str, subject: str, sections: list[str] | None = None,
) -> dict:
    """查询班级长期整体学习状态(整体表现/薄弱点/共性错误/重点关注学生)。

    用于回答班级长期学情,不枚举学生名单;需要班级成员列表时用 list_class_students。
    """
    try:
        async with ProfileAlgorithmV1() as algo:
            data = await algo.compute_class(class_id, subject)
        return ok(_filter_sections(data, sections))
    except TcError as e:
        return fail(e)


def _filter_sections(data: dict, sections: list[str] | None) -> dict:
    """按 sections 过滤画像模块(为空返回完整)。"""
    if not sections:
        return data
    return {k: data[k] for k in sections if k in data}
