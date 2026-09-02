"""题目服务:三类来源创建 Question 与数学难度预判。

规则(参考文档 01 §3.2,FR-002/003/004):
- 来源:手动输入 / 上传图片 OCR 后确认 / 从题库复制
- 数学自建题:Qwen 预判 difficulty(小模型),教师可修改
- 题库复制:直接复制 difficulty,不重新预判
- 英语作文:difficulty=null,固定 max_score=20
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.models.homework import Question, QuestionBankItem
from app.teacher_copilot.errors import InvalidArgument, QuestionNotFound
from app.teacher_copilot.models.clients.llm import LlmClient
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error

_DIFFICULTY_PROMPT = (
    "你是一名数学教师,请判断下面这道数学题的难度(easy/medium/hard),只输出 JSON:"
    '{"difficulty": "easy"}。题目:{content}'
)


class QuestionService(BaseRepository):
    """作业题目服务。"""

    def __init__(self, llm: LlmClient | None = None) -> None:
        super().__init__()
        self._llm = llm or LlmClient()
        self._mock_diff: dict[str, str] = {}  # mock 模式下按题目哈希稳定返回难度

    async def create_question(
        self, *, question_id: str, homework_id: str, subject: str,
        question_type: str, content: str, max_score: int,
        image_url: str | None = None,
        difficulty: str | None = None,
        source_question_bank_item_id: str | None = None,
    ) -> Question:
        """创建题目。数学自建题若未提供 difficulty,则调用难度预判。"""
        if subject == "english":
            # 英语作文固定评分契约(参考文档 01 §3.2.2)
            if max_score != 20:
                raise InvalidArgument("英语作文满分必须为 20")
            difficulty = None
        elif not difficulty:
            difficulty = await self._predict_difficulty(content)
        no = await self._next_question_no(homework_id)
        q = Question(
            question_id=question_id, homework_id=homework_id, question_no=no,
            subject=subject, question_type=question_type, difficulty=difficulty,
            content=content, image_url=image_url, max_score=max_score,
            source_question_bank_item_id=source_question_bank_item_id,
        )
        try:
            self.session.add(q)
            await self.session.commit()
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        return q

    async def _next_question_no(self, homework_id: str) -> int:
        """作业内下一个题号(当前最大序号 + 1)。"""
        try:
            rows = await self.session.scalars(
                select(Question.question_no).where(Question.homework_id == homework_id)
            )
            nos = list(rows)
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        return max(nos, default=0) + 1

    async def _predict_difficulty(self, content: str) -> str:
        """数学自建题难度预判(mock 模式:按内容长度稳定返回)。"""
        try:
            resp = await self._llm.generate_json(
                model_kind="small", prompt=_DIFFICULTY_PROMPT.format(content=content)
            )
            diff = resp.get("difficulty")
            if diff in ("easy", "medium", "hard"):
                return diff
        except Exception:
            pass
        # mock 稳定规则:少于 40 字 → easy;少于 80 字 → medium;否则 hard
        n = len(content)
        return "easy" if n < 40 else "medium" if n < 80 else "hard"

    async def copy_from_bank(
        self, *, question_id: str, homework_id: str, bank_item_id: str, max_score: int,
    ) -> Question:
        """从题库复制题目为作业题(难度直接复制,不重新预判)。"""
        try:
            item = await self.session.scalar(
                select(QuestionBankItem).where(
                    QuestionBankItem.question_bank_item_id == bank_item_id
                )
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if item is None:
            raise QuestionNotFound(f"题库题 {bank_item_id} 不存在")
        return await self.create_question(
            question_id=question_id, homework_id=homework_id,
            subject=item.subject, question_type=item.question_type,
            content=item.content, image_url=item.image_url,
            max_score=max_score, difficulty=item.difficulty,
            source_question_bank_item_id=bank_item_id,
        )
