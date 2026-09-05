"""作业与题目业务 API(教师侧,FR-001~007)。

路由前缀统一 /api/teacher-copilot/homework;认证身份由 DeerFlow Runtime 登录态提供(identity.py:登录用户 → AccountLink → teacher_id)。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.teacher_copilot.api.identity import get_student_id, get_teacher_id
from app.teacher_copilot.api.response import ok
from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import Submission
from app.teacher_copilot.db.models.homework import Homework, Question
from app.teacher_copilot.db.models.org import ClassRoom
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.services.homework_service import HomeworkService
from app.teacher_copilot.services.permission_service import TeacherPermissionService
from app.teacher_copilot.services.question_bank_service import QuestionBankService
from app.teacher_copilot.services.question_service import QuestionService

router = APIRouter(prefix="/api/teacher-copilot/homework")


@router.get("")
@router.get("/")
async def list_homeworks(
    class_id: str | None = None,
    subject: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    teacher_id: str = Depends(get_teacher_id),
):
    """读取当前教师的作业摘要,按班级/学科可选过滤。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_teacher(teacher_id)
        async with HomeworkService() as svc:
            homeworks = await svc.list_homeworks(
                teacher_id,
                class_id=class_id,
                subject=subject,
                limit=limit,
            )
        class_ids = {hw.class_id for hw in homeworks}
        class_names: dict[str, str] = {}
        if class_ids:
            async with get_session() as session:
                rows = await session.execute(
                    select(ClassRoom.class_id, ClassRoom.name).where(
                        ClassRoom.teacher_id == teacher_id,
                        ClassRoom.class_id.in_(class_ids),
                    )
                )
                class_names = {class_id: name for class_id, name in rows}
        return ok([
            {
                "homework_id": hw.homework_id,
                "name": hw.name,
                "class_id": hw.class_id,
                "class_name": class_names.get(hw.class_id, hw.class_id),
                "subject": hw.subject,
                "status": hw.status,
                "deadline": hw.deadline,
                "published_at": hw.published_at,
            }
            for hw in homeworks
        ])
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.post("")      # 无尾斜杠(经 next rewrites 规范化后的实际路径)
@router.post("/")     # 带尾斜杠(原路径,兼容)
async def create_homework(
    body: dict,
    teacher_id: str = Depends(get_teacher_id),
):
    """创建草稿作业。body: {name, class_id, subject, deadline?}"""
    async with TeacherPermissionService() as perm:
        await perm.ensure_teacher(teacher_id)
        await perm.ensure_class_owned(teacher_id, body["class_id"])
    try:
        async with HomeworkService() as svc:
            hw = await svc.create_homework(
                homework_id=f"hw_{await _next_id('hw')}",
                name=body["name"], class_id=body["class_id"],
                teacher_id=teacher_id, subject=body["subject"],
                deadline=body.get("deadline"),
            )
        return ok({"homework_id": hw.homework_id, "status": hw.status})
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/{homework_id}")
async def get_homework(homework_id: str, teacher_id: str = Depends(get_teacher_id)):
    """读取作业与题目列表。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_homework_owned(teacher_id, homework_id)
        async with HomeworkService() as svc:
            hw = await svc.get_homework(homework_id)
            questions = await svc.list_questions(homework_id)
        return ok({
            "homework_id": hw.homework_id, "name": hw.name, "class_id": hw.class_id,
            "subject": hw.subject, "status": hw.status, "published_at": hw.published_at,
            "deadline": hw.deadline,
            "questions": [
                {
                    "question_id": q.question_id, "question_no": q.question_no,
                    "subject": q.subject, "question_type": q.question_type,
                    "difficulty": q.difficulty, "content": q.content,
                    "image_url": q.image_url, "max_score": q.max_score,
                }
                for q in questions
            ],
        })
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.post("/{homework_id}/questions")
async def add_question(homework_id: str, body: dict, teacher_id: str = Depends(get_teacher_id)):
    """添加题目(手动/图片 OCR 后确认)。body: {subject, question_type, content, max_score, difficulty?}"""
    async with TeacherPermissionService() as perm:
        hw = await perm.ensure_homework_owned(teacher_id, homework_id)
    try:
        async with QuestionService() as svc:
            q = await svc.create_question(
                question_id=f"q_{await _next_id('q')}", homework_id=homework_id,
                subject=body.get("subject", hw.subject),
                question_type=body["question_type"],
                content=body["content"], max_score=body["max_score"],
                image_url=body.get("image_url"),
                difficulty=body.get("difficulty"),
            )
        return ok({"question_id": q.question_id, "question_no": q.question_no, "difficulty": q.difficulty})
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/{homework_id}/question-bank")
async def search_bank(
    homework_id: str, subject: str, difficulty: str | None = None,
    knowledge_point: str | None = None,
    teacher_id: str = Depends(get_teacher_id),
):
    """题库检索(Drawer 用;与 Agent Tool 共享 QuestionBankService)。"""
    async with TeacherPermissionService() as perm:
        await perm.ensure_homework_owned(teacher_id, homework_id)
    try:
        async with QuestionBankService() as svc:
            items = await svc.search(
                subject=subject, difficulty=difficulty,
                knowledge_point_keys=[knowledge_point] if knowledge_point else None,
            )
        return ok([
            {
                "question_bank_item_id": i.question_bank_item_id,
                "content": i.content, "difficulty": i.difficulty,
                "question_type": i.question_type, "grade": i.grade,
            }
            for i in items
        ])
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.post("/{homework_id}/publish")
async def publish(homework_id: str, teacher_id: str = Depends(get_teacher_id)):
    """发布作业(校验通过后置 PUBLISHED)。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_homework_owned(teacher_id, homework_id)
        async with HomeworkService() as svc:
            hw = await svc.publish(homework_id)
        return ok({"homework_id": hw.homework_id, "status": hw.status})
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


async def _next_id(prefix: str) -> str:
    """简易 ID 生成(时间戳低 4 位 + 随机后缀;MVP 够用,正式可换 UUID)。"""
    import time

    return f"{int(time.time() * 1000) % 1000000:06d}"

@router.get("/{homework_id}/for-student")
async def homework_for_student(homework_id: str, student_id: str = Depends(get_student_id)):
    """学生视角作业详情:题目列表 + 我在每题的提交状态(US2 学生作业页/批改页)。

    学生属于班级成员即可查看该班作业;提交状态按 (question_id, student_id) 匹配。
    """
    async with get_session() as session:
        hw = await session.scalar(select(Homework).where(Homework.homework_id == homework_id))
        if hw is None:
            raise HTTPException(404, detail=dict(code="HOMEWORK_NOT_FOUND", message="作业不存在"))
        questions = await session.scalars(
            select(Question).where(Question.homework_id == homework_id).order_by(Question.question_no)
        )
        subs = await session.scalars(
            select(Submission).where(Submission.student_id == student_id, Submission.homework_id == homework_id)
        )
        by_q = {sub.question_id: sub for sub in subs}
    return ok({
        "homework": {
            "homework_id": hw.homework_id, "name": hw.name, "class_id": hw.class_id,
            "subject": hw.subject, "status": hw.status, "deadline": hw.deadline,
            "published_at": hw.published_at,
        },
        "questions": [
            {
                "question_id": q.question_id, "question_no": q.question_no,
                "question_type": q.question_type, "content": q.content,
                "max_score": q.max_score, "difficulty": q.difficulty,
                "my_submission": {
                    "submission_id": sub.submission_id,
                    "status": sub.status,
                    "current_stage": sub.current_stage,
                    "score": None,
                } if (sub := by_q.get(q.question_id)) else None,
            }
            for q in questions
        ],
    })
