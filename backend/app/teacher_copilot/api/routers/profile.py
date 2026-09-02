"""画像与分析业务 API(教师侧)。

- profile.py:学生/班级画像 + 批改历史(T058)
- analysis.py:作业分析/题目分析(T051)
认证身份:DeerFlow Runtime 登录态(identity.py → AccountLink → teacher_id)。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import GradingResult
from app.teacher_copilot.db.models.homework import Question
from app.teacher_copilot.api.identity import get_teacher_id
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.services.analysis_service import AnalysisCalculationV1
from app.teacher_copilot.services.permission_service import TeacherPermissionService
from app.teacher_copilot.services.profile_service import ProfileAlgorithmV1

router = APIRouter(prefix="/api/teacher-copilot")


@router.get("/profile/student/{student_id}")
async def student_profile(
    student_id: str, subject: str,
    teacher_id: str = Depends(get_teacher_id),
):
    """获取学生画像(StudentProfile)。"""
    try:
        async with TeacherPermissionService() as perm:
            # student 校验(简化:确认教师存在即可,班级归属查询在真实实现中扩展)
            await perm.ensure_teacher(teacher_id)
        async with ProfileAlgorithmV1() as algo:
            profile = await algo.compute_student(student_id, subject)
        return {"success": True, "data": profile}
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/profile/class/{class_id}")
async def class_profile(
    class_id: str, subject: str,
    teacher_id: str = Depends(get_teacher_id),
):
    """获取班级画像(ClassProfile)。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_teacher(teacher_id)
        async with ProfileAlgorithmV1() as algo:
            profile = await algo.compute_class(class_id, subject)
        return {"success": True, "data": profile}
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/profile/student/{student_id}/history")
async def student_history(
    student_id: str, subject: str, limit: int = 20,
    teacher_id: str = Depends(get_teacher_id),
):
    """学生批改历史(GradingResult[],用于证据下钻)。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_teacher(teacher_id)
        async with get_session() as session:
            rows = await session.scalars(
                select(GradingResult)
                .join(GradingResult.submission)
                .where(GradingResult.subject == subject,
                       GradingResult.submission.has(student_id=student_id))
                .order_by(GradingResult.created_at.desc())
                .limit(limit)
            )
            history = [
                {
                    "grading_result_id": g.grading_result_id,
                    "subject": g.subject, "question_type": g.question_type,
                    "difficulty": g.difficulty,
                    "score": {"earned": g.score_earned, "max": g.score_max, "rate": g.score_rate},
                    "feedback": g.feedback,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
                for g in rows
            ]
        return {"success": True, "data": history}
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/analysis/homework/{homework_id}")
async def homework_analysis(
    homework_id: str, class_id: str,
    teacher_id: str = Depends(get_teacher_id),
):
    """作业分析(HomeworkAnalysis,即时聚合)。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_homework_owned(teacher_id, homework_id)
        async with AnalysisCalculationV1() as algo:
            analysis = await algo.compute_homework_analysis(homework_id, class_id)
        return {"success": True, "data": analysis}
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/analysis/question/{question_id}")
async def question_analysis(
    question_id: str, homework_id: str, class_id: str,
    teacher_id: str = Depends(get_teacher_id),
):
    """单题下钻分析(QuestionAnalysis,即时聚合)。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_question_owned(teacher_id, question_id)
        async with AnalysisCalculationV1() as algo:
            # 复用作业分析,过滤该题
            full = await algo.compute_homework_analysis(homework_id, class_id)
        # 找到该题的 QuestionStat
        qs = next((q for q in full["questions"] if q["question_id"] == question_id), None)
        if qs is None:
            raise HTTPException(404, detail=dict(code="QUESTION_NOT_FOUND", message="题目无有效作答数据"))
        return {"success": True, "data": qs}
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))
