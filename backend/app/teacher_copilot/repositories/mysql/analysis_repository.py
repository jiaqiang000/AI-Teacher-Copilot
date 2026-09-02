"""分析统计查询仓:仅取当前有效的成功批改事实。

有效事实范围(data-model.md §5.2 / 参考文档 03 §3.8.1):
submission.status = SUCCEEDED 且当前 GradingResult 仍存在。
PENDING/RUNNING/FAILED/已删除旧结果均不进入统计。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.teacher_copilot.db.models.grading import (
    GradingResult,
    GradingResultError,
    GradingResultKnowledgePoint,
    Submission,
)
from app.teacher_copilot.db.models.homework import Question
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error


class AnalysisRepository(BaseRepository):
    """分析所需的当前有效事实查询。"""

    async def list_valid_grading_results(self, homework_id: str) -> list[GradingResult]:
        """某作业下所有当前有效成功批改结果(含诊断子表)。"""
        try:
            rows = await self.session.scalars(
                select(GradingResult)
                .join(Submission, Submission.submission_id == GradingResult.submission_id)
                .where(Submission.homework_id == homework_id)
                .options(
                    selectinload(GradingResult._kp_rows),
                    selectinload(GradingResult._error_rows),
                )
            )
            return list(rows)
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def list_questions(self, homework_id: str) -> list[Question]:
        """作业题目列表(按题号升序)。"""
        try:
            rows = await self.session.scalars(
                select(Question).where(Question.homework_id == homework_id)
                .order_by(Question.question_no)
            )
            return list(rows)
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def list_students(self, class_id: str) -> list[str]:
        """班级学生 ID 列表。"""
        from app.teacher_copilot.db.models.org import ClassStudent

        try:
            rows = await self.session.scalars(
                select(ClassStudent.student_id).where(ClassStudent.class_id == class_id)
            )
            return list(rows)
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc


# 在 GradingResult 上挂载关系(为 selectinload 提供),见 grading.py 中的 relationship
