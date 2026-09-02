"""业务对象解析(Business Object Resolution,参考文档 05 §1.1 / 06-07 §2.5)。

教师自然语言"张三/八三班/这次作业/第 8 题" → 明确业务 ID 的轻量解析。
四原则:Context First(上下文优先)/ Unique Match First(唯一匹配直接继续)/
Clarify on Ambiguity(歧义才询问)/ Never Guess ID(禁止猜测业务 ID)。

不新增 Entity Resolution Agent / Tool;歧义走 DeerFlow ask_clarification(HITL)。
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.homework import Homework, Question
from app.teacher_copilot.db.models.org import ClassRoom, ClassStudent, Student

logger = logging.getLogger("teacher_copilot.resolution")


async def resolve_student(class_id: str | None, name: str, context: dict | None = None) -> dict:
    """按姓名解析学生。

    返回:{"student_id": ..., "ambiguity": bool, "candidates": [...]}。
    ambiguous=True 时调用方应走 ask_clarification 请教师确认。
    """
    # Context First:当前页面已明确学生
    if context and context.get("current_student_id"):
        return {"student_id": context["current_student_id"], "ambiguity": False, "candidates": []}
    async with get_session() as session:
        stmt = select(Student.student_id, Student.name).where(Student.name == name)
        if class_id:
            stmt = stmt.join(ClassStudent, ClassStudent.student_id == Student.student_id).where(
                ClassStudent.class_id == class_id
            )
        rows = list(await session.execute(stmt))
    if not rows:
        return {"student_id": None, "ambiguity": True, "candidates": []}
    if len(rows) == 1:
        return {"student_id": rows[0][0], "ambiguity": False, "candidates": []}
    return {"student_id": None, "ambiguity": True, "candidates": [r[0] for r in rows]}


async def resolve_class(name: str, context: dict | None = None) -> dict:
    """按班级名解析班级(仅姓名唯一匹配;同名校返回歧义)。"""
    async with get_session() as session:
        rows = list(await session.execute(
            select(ClassRoom.class_id, ClassRoom.name).where(ClassRoom.name == name)
        ))
    if len(rows) == 1:
        return {"class_id": rows[0][0], "ambiguity": False, "candidates": []}
    return {"class_id": None, "ambiguity": True, "candidates": [r[0] for r in rows]}


async def resolve_question(homework_id: str | None, question_no: int | None,
                           context: dict | None = None) -> dict:
    """按题号解析题目(优先 Context 中 homework_id + question_refs)。"""
    if context and context.get("current_question_id") and question_no is None:
        return {"question_id": context["current_question_id"], "ambiguity": False}
    if homework_id is None:
        homework_id = (context or {}).get("current_homework_id")
    if homework_id is None:
        return {"question_id": None, "ambiguity": True, "candidates": []}
    async with get_session() as session:
        q = await session.scalar(
            select(Question.question_id).where(
                Question.homework_id == homework_id, Question.question_no == question_no
            )
        )
    if q:
        return {"question_id": q, "ambiguity": False, "candidates": []}
    return {"question_id": None, "ambiguity": True, "candidates": []}


async def resolve_homework(class_id: str | None, name_hint: str | None,
                           context: dict | None = None) -> dict:
    """按作业名/当前作业上下文解析作业。"""
    if context and context.get("current_homework_id"):
        return {"homework_id": context["current_homework_id"], "ambiguity": False}
    if not name_hint:
        return {"homework_id": None, "ambiguity": True, "candidates": []}
    async with get_session() as session:
        stmt = select(Homework.homework_id, Homework.name).where(Homework.name == name_hint)
        if class_id:
            stmt = stmt.where(Homework.class_id == class_id)
        rows = list(await session.execute(stmt))
    if len(rows) == 1:
        return {"homework_id": rows[0][0], "ambiguity": False, "candidates": []}
    return {"homework_id": None, "ambiguity": True, "candidates": [r[0] for r in rows]}
