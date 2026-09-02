"""题库服务:条件查询题库题(与 search_question_bank Tool 共享)。

规则(参考文档 03 §3.2.7 / 05 §13.9):
- 只返回 QuestionBankItem,不返回 Homework 已布置的 Question
- 知识点标签与画像使用同一套标准 level=2 Taxonomy
- 多个 knowledge_point_keys 默认"至少命中其中一个"
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.models.homework import QuestionBankItem, QuestionBankItemKnowledgePoint
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error


class QuestionBankService(BaseRepository):
    """题库检索(教师 UI 题库 Drawer 与 Agent Tool 共用)。"""

    async def search(
        self, *, subject: str, knowledge_point_keys: list[str] | None = None,
        difficulty: str | None = None, question_type: str | None = None,
        grade: str | None = None, count: int = 20,
        exclude_question_bank_item_ids: list[str] | None = None,
    ) -> list[QuestionBankItem]:
        """条件查询题库题。"""
        try:
            stmt = select(QuestionBankItem).where(QuestionBankItem.subject == subject)
            if difficulty:
                stmt = stmt.where(QuestionBankItem.difficulty == difficulty)
            if question_type:
                stmt = stmt.where(QuestionBankItem.question_type == question_type)
            if grade:
                stmt = stmt.where(QuestionBankItem.grade == grade)
            if exclude_question_bank_item_ids:
                stmt = stmt.where(
                    QuestionBankItem.question_bank_item_id.not_in(exclude_question_bank_item_ids)
                )
            if knowledge_point_keys:
                # 至少命中其中一个知识点(参考文档 05 §13.9)
                sub = select(QuestionBankItemKnowledgePoint.question_bank_item_id).where(
                    QuestionBankItemKnowledgePoint.knowledge_point_key.in_(knowledge_point_keys)
                )
                stmt = stmt.where(QuestionBankItem.question_bank_item_id.in_(sub))
            stmt = stmt.limit(count)
            return list(await self.session.scalars(stmt))
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def get_item(self, item_id: str) -> QuestionBankItem | None:
        """按 ID 读取题库题。"""
        try:
            return await self.session.scalar(
                select(QuestionBankItem).where(
                    QuestionBankItem.question_bank_item_id == item_id
                )
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
