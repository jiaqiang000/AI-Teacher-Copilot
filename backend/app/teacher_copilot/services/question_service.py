"""题目服务:三类来源创建 Question 与数学难度预判。

规则(参考文档 01 §3.2,FR-002/003/004):
- 来源:手动输入 / 上传图片 OCR 后确认 / 从题库复制
- 数学自建题:小模型预判 difficulty,教师可修改;模型未给出合法难度时显式报错,
  由教师手动输入,**不按题干字数猜测**(008 FR-008)
- 题库复制:直接复制 difficulty,不重新预判
- 英语作文:difficulty=null,固定 max_score=20
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.teacher_copilot.db.models.homework import Question, QuestionBankItem
from app.teacher_copilot.errors import InvalidArgument, QuestionNotFound, TcError
from app.teacher_copilot.models.clients.llm import LlmClient
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error

logger = logging.getLogger("teacher_copilot.question")

_DIFFICULTY_PROMPT = (
    "你是一名数学教师,请判断下面这道数学题的难度(easy/medium/hard),只输出 JSON:"
    # 示例 JSON 的花括号须转义,否则 str.format 会把 {"difficulty": ...} 当成占位符,
    # 每次都抛 KeyError——此前该异常被静默兜底吞掉,导致"模型预判"实际从未执行
    '{{"difficulty": "easy"}}。题目:{content}'
)

# 难度预判失败时的统一提示:面向教师,明确要求手动输入
_DIFFICULTY_UNDETERMINED_HINT = "无法自动判定题目难度,请手动选择难度后重试"


class QuestionService(BaseRepository):
    """作业题目服务。"""

    def __init__(self, llm: LlmClient | None = None) -> None:
        super().__init__()
        self._llm = llm or LlmClient()

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
        else:
            # 数学满分必须为正(008 T042):0 或负数会让得分率兜底成 0,
            # 把这道题以及班级平均分一起拉低
            if max_score <= 0:
                raise InvalidArgument("题目满分必须大于 0")
            if not difficulty:
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
        """数学自建题难度预判(只采信模型返回的合法档位)。

        模型未返回 easy/medium/hard 时显式失败,由教师手动输入(008 FR-008)。
        原先"按题干字数猜测"的兜底已移除:那种猜测会把"模型没给出难度"伪装成
        一个看起来合理的档位,使问题永远暴露不出来。
        注意保留的是**预判能力本身**(参考方案:预判 → 教师确认 / 修改),
        移除的只是猜测兜底。
        """
        try:
            resp = await self._llm.generate_json(
                model_kind="small", prompt=_DIFFICULTY_PROMPT.format(content=content)
            )
        except TcError:
            # 专用错误码(如 MODEL_NOT_CONFIGURED)直接上报,便于定位根因
            raise
        except Exception as exc:
            # 这条路径原先是"静默降级 + 字数猜测"的兜底点,按 FR-003 记 ERROR,
            # 并带上足以定位的上下文(题干长度而非题干原文,避免把题目内容写进日志)
            logger.error(
                "难度预判调用失败,改由教师手动输入: content_len=%d, err=%s",
                len(content), exc,
            )
            raise InvalidArgument(
                _DIFFICULTY_UNDETERMINED_HINT, code="DIFFICULTY_UNDETERMINED"
            ) from exc
        diff = resp.get("difficulty")
        if diff not in ("easy", "medium", "hard"):
            logger.error(
                "难度预判返回非法值 %r,改由教师手动输入: content_len=%d",
                diff, len(content),
            )
            raise InvalidArgument(
                _DIFFICULTY_UNDETERMINED_HINT, code="DIFFICULTY_UNDETERMINED"
            )
        return diff

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
