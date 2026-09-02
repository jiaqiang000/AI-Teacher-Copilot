"""提交服务:创建/拦截/重交 Submission(FR-009~011)。

规则(参考文档 01 §3.4,按 contracts/grading-api.md):
- 同一 student_id + question_id 只保留一条当前 Submission(UNIQUE 约束)
- PENDING/RUNNING → 拒绝再次提交(HTTP 409 SUBMISSION_GRADING_IN_PROGRESS)
- SUCCEEDED/FAILED → 复用原 submission_id:替换 image_url、删除旧 OCRResult/
  GradingResult、重置状态与时间字段,重新执行 Workflow
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select

from app.teacher_copilot.db.models.grading import (
    GradingResult,
    GradingResultError,
    GradingResultKnowledgePoint,
    OcrResult,
    Submission,
)
from app.teacher_copilot.errors import GradingInProgress, SubmissionNotFound
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error


class SubmissionService(BaseRepository):
    """Submission 生命周期服务。"""

    def _build_id(self) -> str:
        import time

        return f"sub_{int(time.time() * 1000) % 100000000:08d}"

    async def submit(
        self, *, student_id: str, question_id: str, homework_id: str, image_url: str,
    ) -> tuple[Submission, bool]:
        """提交答案。返回 (Submission, 是否新建)。

        已存在且 PENDING/RUNNING → 抛 GradingInProgress;
        已存在且 SUCCEEDED/FAILED → 复用并重置(清除旧 OCRResult/GradingResult)。
        """
        try:
            existing = await self.session.scalar(
                select(Submission).where(
                    Submission.student_id == student_id,
                    Submission.question_id == question_id,
                )
            )
            if existing is None:
                sub = Submission(
                    submission_id=self._build_id(), student_id=student_id,
                    question_id=question_id, homework_id=homework_id,
                    image_url=image_url, status="PENDING", current_stage="QUEUED",
                )
                self.session.add(sub)
                await self.session.commit()
                return sub, True

            if existing.status in ("PENDING", "RUNNING"):
                raise GradingInProgress(
                    "该题正在批改中,请等待批改完成后再重新提交。",
                    code="SUBMISSION_GRADING_IN_PROGRESS",
                )

            # SUCCEEDED / FAILED:复用原 submission_id 重交
            await self._clean_old_results(existing.submission_id)
            existing.image_url = image_url
            existing.status = "PENDING"
            existing.current_stage = "QUEUED"
            existing.error_code = None
            existing.error_message = None
            existing.started_at = None
            existing.finished_at = None
            existing.submitted_at = datetime.utcnow()
            await self.session.commit()
            return existing, False
        except GradingInProgress:
            raise
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def _clean_old_results(self, submission_id: str) -> None:
        """清除旧的当前 OCRResult / GradingResult(含诊断子表)。"""
        for model in (GradingResultKnowledgePoint, GradingResultError):
            sub = select(GradingResult.grading_result_id).where(
                GradingResult.submission_id == submission_id
            )
            await self.session.execute(delete(model).where(model.grading_result_id.in_(sub)))
        await self.session.execute(
            delete(GradingResult).where(GradingResult.submission_id == submission_id)
        )
        await self.session.execute(
            delete(OcrResult).where(OcrResult.submission_id == submission_id)
        )

    async def get(self, submission_id: str) -> Submission:
        """读取当前 Submission(页面刷新恢复的事实源)。"""
        try:
            sub = await self.session.scalar(
                select(Submission).where(Submission.submission_id == submission_id)
            )
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if sub is None:
            raise SubmissionNotFound(f"提交 {submission_id} 不存在")
        return sub

    async def set_stage(self, submission_id: str, status: str, stage: str) -> None:
        """更新批改状态与阶段(每阶段变化先落库,再发事件)。"""
        try:
            sub = await self.session.scalar(
                select(Submission).where(Submission.submission_id == submission_id)
            )
            if sub is None:
                return
            sub.status = status
            sub.current_stage = stage
            if stage == "OCR" and sub.started_at is None:
                sub.started_at = datetime.utcnow()
            if status == "SUCCEEDED":
                sub.finished_at = datetime.utcnow()
            await self.session.commit()
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def set_failed(self, submission_id: str, error_code: str, message: str) -> None:
        """标记批改失败(保存错误供前端展示与排查)。"""
        try:
            sub = await self.session.scalar(
                select(Submission).where(Submission.submission_id == submission_id)
            )
            if sub is None:
                return
            sub.status = "FAILED"
            sub.current_stage = "FAILED"
            sub.error_code = error_code
            sub.error_message = message
            sub.finished_at = datetime.utcnow()
            await self.session.commit()
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
