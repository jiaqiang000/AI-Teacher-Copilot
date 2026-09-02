"""题库检索 Tool(search_question_bank)。

只返回 QuestionBankItem(独立题库资源),不返回已布置的 Homework Question
(参考文档 03 §5.9、05 §13.9);与教师 UI 题库 Drawer 共享 QuestionBankService。
异步实现(Agent 运行时调用)。
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.services.question_bank_service import QuestionBankService
from app.teacher_copilot.tools.schemas.inputs import SearchQuestionBankInput


@tool("search_question_bank", args_schema=SearchQuestionBankInput)
async def search_question_bank(
    subject: str, knowledge_point_keys: list[str],
    difficulty: str | None = None, question_type: str | None = None,
    grade: str | None = None, count: int = 10,
    exclude_question_bank_item_ids: list[str] | None = None,
) -> dict:
    """按标准知识点、难度、题型、年级检索系统题库练习题,用于分层/个性化练习选题。

    只返回 QuestionBankItem(题库资源),不返回已布置到作业的题目。
    多个知识点表示"至少命中其中一个";为多个知识点分别找题应分别查询。
    """
    try:
        async with QuestionBankService() as svc:
            items = await svc.search(
                subject=subject, knowledge_point_keys=knowledge_point_keys,
                difficulty=difficulty, question_type=question_type,
                grade=grade, count=count,
                exclude_question_bank_item_ids=exclude_question_bank_item_ids,
            )
            return ok([{
                "question_bank_item_id": i.question_bank_item_id,
                "content": i.content, "image_url": i.image_url,
                "subject": i.subject, "grade": i.grade,
                "difficulty": i.difficulty, "question_type": i.question_type,
                "reference_answer": i.reference_answer,
            } for i in items])
    except TcError as e:
        return fail(e)
