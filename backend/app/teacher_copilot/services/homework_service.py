"""作业服务:创建/编辑/发布 Homework 与业务校验。

业务规则(参考文档 01 §3.1/3.3,FR-001/005/006/041):
- 状态仅 DRAFT / PUBLISHED;DRAFT 可增删改题目,PUBLISHED 后不可修改题目
- 发布前校验:至少 1 题、题号唯一、content 非空、max_score>0、
  数学 difficulty 非空、英语 essay max_score=20、subject 与作业一致
- deadline 可选(仅展示,不做逾期拦截)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.teacher_copilot.db.models.homework import Homework, Question
from app.teacher_copilot.errors import HomeworkNotFound, InvalidArgument
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error


class HomeworkService(BaseRepository):
    """作业生命周期服务。"""

    async def create_homework(
        self, *, homework_id: str, name: str, class_id: str, teacher_id: str,
        subject: str, deadline: datetime | None = None,
    ) -> Homework:
        """创建草稿作业(允许携带可选截止时间)。"""
        try:
            hw = Homework(
                homework_id=homework_id, name=name, class_id=class_id,
                teacher_id=teacher_id, subject=subject, status="DRAFT",
                deadline=deadline,
            )
            self.session.add(hw)
            await self.session.commit()
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        return hw

    async def get_homework(self, homework_id: str) -> Homework:
        """按 ID 读取作业(题目预加载)。"""
        try:
            hw = await self.session.scalar(
                select(Homework).where(Homework.homework_id == homework_id)
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if hw is None:
            raise HomeworkNotFound(f"作业 {homework_id} 不存在")
        return hw

    async def list_questions(self, homework_id: str) -> list[Question]:
        """作业题目列表(按题号升序)。"""
        try:
            rows = await self.session.scalars(
                select(Question)
                .where(Question.homework_id == homework_id)
                .order_by(Question.question_no)
            )
            return list(rows)
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def publish(self, homework_id: str) -> Homework:
        """发布作业:先做发布前校验,再置 PUBLISHED 与 published_at。"""
        hw = await self.get_homework(homework_id)
        if hw.status == "PUBLISHED":
            return hw
        questions = await self.list_questions(homework_id)
        if not questions:
            raise InvalidArgument("作业至少需要 1 道题目")
        nos = [q.question_no for q in questions]
        if len(nos) != len(set(nos)):
            raise InvalidArgument("题目序号重复,请调整题号")
        for q in questions:
            if not q.content:
                raise InvalidArgument(f"第 {q.question_no} 题内容为空")
            if q.max_score <= 0:
                raise InvalidArgument(f"第 {q.question_no} 题满分必须大于 0")
            if q.subject != hw.subject:
                raise InvalidArgument(f"第 {q.question_no} 题学科与作业不一致")
            if q.subject == "math" and not q.difficulty:
                raise InvalidArgument(f"第 {q.question_no} 题数学难度未确定")
            if q.subject == "english" and q.max_score != 20:
                raise InvalidArgument("英语作文满分必须为 20")
        hw.status = "PUBLISHED"
        hw.published_at = datetime.utcnow()
        try:
            await self.session.commit()
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        return hw
