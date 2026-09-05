"""教师业务权限校验服务。

权限链路(参考 docs/05-tool-skill.md §10):
可信登录身份(Runtime Context)→ teacher_id → 校验对象(班级/学生/作业/题目)归属。
禁止让 LLM 在 Tool 参数中自报 teacher_id。
MVP 只做必要教师数据隔离与对象归属校验,不引入复杂 RBAC(宪法 V)。
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.models.homework import Homework, Question
from app.teacher_copilot.db.models.org import ClassRoom, ClassStudent, Teacher
from app.teacher_copilot.errors import PermissionDenied, QuestionNotFound
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error


class TeacherPermissionService(BaseRepository):
    """校验当前教师对业务对象的访问权限。"""

    async def ensure_teacher(self, teacher_id: str) -> None:
        """确认教师存在,否则视为无权限。"""
        try:
            found = await self.session.scalar(
                select(Teacher).where(Teacher.teacher_id == teacher_id)
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if found is None:
            raise PermissionDenied(f"教师 {teacher_id} 不存在或无权限")

    async def ensure_class_owned(self, teacher_id: str, class_id: str) -> ClassRoom:
        """校验班级归属当前教师并返回班级实体,供页面展示真实名称。"""
        try:
            found = await self.session.scalar(
                select(ClassRoom).where(
                    ClassRoom.class_id == class_id,
                    ClassRoom.teacher_id == teacher_id,
                )
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if found is None:
            raise PermissionDenied(f"无权访问班级 {class_id}")
        return found

    async def ensure_student_in_class(self, teacher_id: str, class_id: str, student_id: str) -> None:
        """校验学生属于当前教师的班级。"""
        await self.ensure_class_owned(teacher_id, class_id)
        try:
            found = await self.session.scalar(
                select(ClassStudent).where(
                    ClassStudent.class_id == class_id,
                    ClassStudent.student_id == student_id,
                )
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if found is None:
            raise PermissionDenied(f"无权访问学生 {student_id}")

    async def ensure_homework_owned(self, teacher_id: str, homework_id: str) -> Homework:
        """校验作业归属当前教师,返回 Homework 实体。"""
        try:
            hw = await self.session.scalar(
                select(Homework).where(Homework.homework_id == homework_id)
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if hw is None or hw.teacher_id != teacher_id:
            raise PermissionDenied(f"无权访问作业 {homework_id}")
        return hw

    async def ensure_question_owned(self, teacher_id: str, question_id: str) -> Question:
        """校验题目归属(题目 → 作业 → 教师),返回 Question 实体。"""
        try:
            q = await self.session.scalar(
                select(Question).where(Question.question_id == question_id)
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if q is None:
            raise QuestionNotFound(f"题目 {question_id} 不存在")
        await self.ensure_homework_owned(teacher_id, q.homework_id)
        return q
