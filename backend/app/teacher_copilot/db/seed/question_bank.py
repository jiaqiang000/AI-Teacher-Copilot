"""题库种子:12 道数学题库题(依据参考文档 08 §3.2 Question Bank Fixture)。

题库题加入作业时复制为新 Question(见 homework.py 的 source_question_bank_item_id),
本种子只提供系统预置的可复用题库资源。
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.homework import QuestionBankItem, QuestionBankItemKnowledgePoint

# (id, grade, knowledge_point_keys, difficulty, question_type, 题目摘要)
FIXTURE: list[tuple[str, str, list[str], str, str, str]] = [
    ("qb_001", "8", ["math.linear_equation.transposition"], "easy", "calculation", "解方程 x + 5 = 12"),
    ("qb_002", "8", ["math.linear_equation.transposition"], "easy", "calculation", "解方程 3x - 4 = 11"),
    ("qb_003", "8", ["math.linear_equation.transposition"], "medium", "solution", "解方程 2(x-3)=x+5 并写过程"),
    ("qb_004", "8", ["math.linear_equation.transposition"], "medium", "solution", "解含括号的一元一次方程"),
    ("qb_005", "8", ["math.linear_equation.transposition"], "hard", "solution", "一元一次方程综合应用"),
    ("qb_006", "8", ["math.function.graph"], "easy", "calculation", "读取函数图像上的点坐标"),
    ("qb_007", "8", ["math.function.graph"], "medium", "solution", "根据函数图像判断增减变化"),
    ("qb_008", "8", ["math.function.graph"], "hard", "solution", "函数图像综合信息读取"),
    ("qb_009", "8", ["math.linear_equation.combine_like_terms"], "easy", "calculation", "合并同类项后求解方程"),
    ("qb_010", "8", ["math.linear_equation.combine_like_terms"], "medium", "solution", "多项式合并后求解"),
    ("qb_011", "8", ["math.linear_equation.transposition", "math.linear_equation.combine_like_terms"], "medium", "solution", "移项并合并同类项综合题"),
    ("qb_012", "8", ["math.function.graph"], "medium", "solution", "根据图像比较两个函数值"),
]


async def seed_question_bank() -> None:
    """写入题库 Fixture(幂等;知识点关联同步写入)。"""
    async with get_session() as session:
        for item_id, grade, kp_keys, difficulty, qtype, content in FIXTURE:
            exists = await session.scalar(
                select(QuestionBankItem).where(QuestionBankItem.question_bank_item_id == item_id)
            )
            if exists is not None:
                continue
            session.add(QuestionBankItem(
                question_bank_item_id=item_id,
                subject="math",
                grade=grade,
                question_type=qtype,
                difficulty=difficulty,
                content=content,
                reference_answer="",
                tags="",
            ))
            for kp in kp_keys:
                session.add(QuestionBankItemKnowledgePoint(
                    question_bank_item_id=item_id, knowledge_point_key=kp
                ))
        await session.commit()
