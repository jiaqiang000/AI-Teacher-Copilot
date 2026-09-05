"""画像与分析业务 API(教师侧)。

- profile.py:学生/班级画像 + 批改历史(T058)
- analysis.py:作业分析/题目分析(T051)
认证身份:DeerFlow Runtime 登录态(identity.py → AccountLink → teacher_id)。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.teacher_copilot.api.identity import get_teacher_id
from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import GradingResult
from app.teacher_copilot.db.models.org import ClassRoom, ClassStudent, Student
from app.teacher_copilot.errors import StudentNotFound, TcError
from app.teacher_copilot.services.analysis_service import AnalysisCalculationV1
from app.teacher_copilot.services.permission_service import TeacherPermissionService
from app.teacher_copilot.services.profile_service import ProfileAlgorithmV1

router = APIRouter(prefix="/api/teacher-copilot")


@router.get("/classes")
async def teacher_classes(teacher_id: str = Depends(get_teacher_id)):
    """读取当前教师的真实班级列表和成员数量。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_teacher(teacher_id)
        async with get_session() as session:
            rows = await session.execute(
                select(
                    ClassRoom.class_id,
                    ClassRoom.name,
                    func.count(ClassStudent.student_id).label("student_count"),
                )
                .outerjoin(ClassStudent, ClassStudent.class_id == ClassRoom.class_id)
                .where(ClassRoom.teacher_id == teacher_id)
                .group_by(ClassRoom.class_id, ClassRoom.name)
                .order_by(ClassRoom.class_id)
            )
            data = [
                {
                    "class_id": class_id,
                    "name": name,
                    "student_count": student_count,
                }
                for class_id, name, student_count in rows
            ]
        return {"success": True, "data": data}
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/profile/student/{student_id}")
async def student_profile(
    student_id: str, subject: str, class_id: str | None = None,
    teacher_id: str = Depends(get_teacher_id),
):
    """获取学生画像(StudentProfile)。"""
    try:
        student, class_room = await _teacher_student_context(
            teacher_id, student_id, class_id,
        )
        async with TeacherPermissionService() as perm:
            await perm.ensure_teacher(teacher_id)
        async with ProfileAlgorithmV1() as algo:
            profile = await algo.compute_student(student_id, subject)
        profile["basic"].update({
            "student_name": student.name,
            "class_id": class_room.class_id,
            "class_name": class_room.name,
        })
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
            class_room = await perm.ensure_class_owned(teacher_id, class_id)
        async with ProfileAlgorithmV1() as algo:
            profile = await algo.compute_class(class_id, subject)
        profile["basic"]["class_name"] = class_room.name
        return {"success": True, "data": profile}
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/profile/student/{student_id}/history")
async def student_history(
    student_id: str, subject: str, class_id: str | None = None, limit: int = 20,
    teacher_id: str = Depends(get_teacher_id),
):
    """学生批改历史(GradingResult[],用于证据下钻)。"""
    try:
        await _teacher_student_context(teacher_id, student_id, class_id)
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


async def _teacher_student_context(
    teacher_id: str, student_id: str, class_id: str | None,
) -> tuple[Student, ClassRoom]:
    """读取教师可见的学生及班级,无匹配时禁止用其他学生或班级兜底。"""
    async with get_session() as session:
        stmt = (
            select(Student, ClassRoom)
            .join(ClassStudent, ClassStudent.student_id == Student.student_id)
            .join(ClassRoom, ClassRoom.class_id == ClassStudent.class_id)
            .where(
                Student.student_id == student_id,
                ClassRoom.teacher_id == teacher_id,
            )
            .order_by(ClassRoom.class_id)
            .limit(1)
        )
        if class_id:
            stmt = stmt.where(ClassRoom.class_id == class_id)
        row = (await session.execute(stmt)).first()
    if row is None:
        raise StudentNotFound(f"学生 {student_id} 不存在或不属于当前教师班级")
    return row


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
