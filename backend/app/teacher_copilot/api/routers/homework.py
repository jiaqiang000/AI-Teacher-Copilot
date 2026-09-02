"""作业与题目业务 API(教师侧,FR-001~007)。

路由前缀统一 /api/teacher-copilot/homework;认证身份由 DeerFlow Gateway
AuthMiddleware 提供,本层用 header X-Teacher-Id 作为 MVP 可信身份占位
(实现阶段按 DeerFlow Runtime Context 替换,参考 permission_service 注释)。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.services.homework_service import HomeworkService
from app.teacher_copilot.services.permission_service import TeacherPermissionService
from app.teacher_copilot.services.question_bank_service import QuestionBankService
from app.teacher_copilot.services.question_service import QuestionService

router = APIRouter(prefix="/api/teacher-copilot/homework")


@router.post("/")
async def create_homework(
    body: dict,
    x_teacher_id: str = Header(default="teacher_01"),
):
    """创建草稿作业。body: {name, class_id, subject, deadline?}"""
    async with TeacherPermissionService() as perm:
        await perm.ensure_teacher(x_teacher_id)
        await perm.ensure_class_owned(x_teacher_id, body["class_id"])
    try:
        async with HomeworkService() as svc:
            hw = await svc.create_homework(
                homework_id=f"hw_{await _next_id('hw')}",
                name=body["name"], class_id=body["class_id"],
                teacher_id=x_teacher_id, subject=body["subject"],
                deadline=body.get("deadline"),
            )
        return ok({"homework_id": hw.homework_id, "status": hw.status})
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


@router.get("/{homework_id}")
async def get_homework(homework_id: str, x_teacher_id: str = Header(default="teacher_01")):
    """读取作业与题目列表。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_homework_owned(x_teacher_id, homework_id)
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
async def add_question(homework_id: str, body: dict, x_teacher_id: str = Header(default="teacher_01")):
    """添加题目(手动/图片 OCR 后确认)。body: {subject, question_type, content, max_score, difficulty?}"""
    async with TeacherPermissionService() as perm:
        hw = await perm.ensure_homework_owned(x_teacher_id, homework_id)
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
    x_teacher_id: str = Header(default="teacher_01"),
):
    """题库检索(Drawer 用;与 Agent Tool 共享 QuestionBankService)。"""
    async with TeacherPermissionService() as perm:
        await perm.ensure_homework_owned(x_teacher_id, homework_id)
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
async def publish(homework_id: str, x_teacher_id: str = Header(default="teacher_01")):
    """发布作业(校验通过后置 PUBLISHED)。"""
    try:
        async with TeacherPermissionService() as perm:
            await perm.ensure_homework_owned(x_teacher_id, homework_id)
        async with HomeworkService() as svc:
            hw = await svc.publish(homework_id)
        return ok({"homework_id": hw.homework_id, "status": hw.status})
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))


async def _next_id(prefix: str) -> str:
    """简易 ID 生成(时间戳低 4 位 + 随机后缀;MVP 够用,正式可换 UUID)。"""
    import time

    return f"{int(time.time() * 1000) % 1000000:06d}"
