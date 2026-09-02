"""批改链路 ORM:submission / ocr_result / grading_result 及诊断子表。

字段依据 data-model.md §2.3/§2.4;核心约束:
- submission UNIQUE(student_id, question_id)(同一学生同一题只保留一条当前提交)
- grading_result 与 ocr_result 均为"当前有效"单条,重新提交时删除旧记录
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.teacher_copilot.db.engine import Base


class Submission(Base):
    """学生对某道题当前有效的答案 + 当前批改生命周期状态。"""

    __tablename__ = "submission"
    # 同一学生同一题最多一条当前提交(参考文档 01 §3.4)
    __table_args__ = (
        UniqueConstraint("student_id", "question_id", name="uq_student_question_submission"),
    )

    submission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64))
    question_id: Mapped[str] = mapped_column(String(64))
    homework_id: Mapped[str] = mapped_column(String(64))
    image_url: Mapped[str] = mapped_column(String(512))  # 当前答案图片(业务资产)
    # 生命周期:PENDING / RUNNING / SUCCEEDED / FAILED
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    # 执行阶段(RUNNING 时):QUEUED/OCR/PARSING/GRADING/ASSEMBLING_RESULT/COMPLETED
    current_stage: Mapped[str] = mapped_column(String(32), default="QUEUED")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关联批改结果(US3/US4 分析用)
    _grading_result_rows: Mapped[list["GradingResult"]] = relationship(
        back_populates="submission", lazy="selectin"
    )


class OcrResult(Base):
    """学生作答图片的 OCR 识别证据(当前 Submission 最多一条)。"""

    __tablename__ = "ocr_result"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_ocr_result_submission"),
    )

    ocr_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(64), ForeignKey("submission.submission_id"))
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="SUCCEEDED")
    md_results: Mapped[str | None] = mapped_column(Text, nullable=True)  # 整体 Markdown 结果
    # Block 数组(JSON):index/label/content/bbox2d/width/height
    layout_details: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GradingResult(Base):
    """当前 Submission 成功批改后的唯一最终结果(统一 Common + 数学/英语详情)。"""

    __tablename__ = "grading_result"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_grading_result_submission"),
    )

    grading_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(64), ForeignKey("submission.submission_id"))
    subject: Mapped[str] = mapped_column(String(16))
    question_type: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 英语 null
    score_earned: Mapped[float] = mapped_column(Float)
    score_max: Mapped[float] = mapped_column(Float)
    score_rate: Mapped[float] = mapped_column(Float)
    # feedback:{summary, strengths[], improvements[]}
    feedback: Mapped[dict] = mapped_column(JSON, default=dict)
    # 数学详情:{correct, final_answer, steps[]}(可空)
    math_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 英语作文详情:{dimension_scores, language_errors[], evidence}(可空)
    english_essay_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 执行元数据:{route, models_used[]}
    execution_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 诊断子表关系(selectinload 用)
    _kp_rows: Mapped[list["GradingResultKnowledgePoint"]] = relationship(
        back_populates="_grading_result", lazy="selectin"
    )
    _error_rows: Mapped[list["GradingResultError"]] = relationship(
        back_populates="_grading_result", lazy="selectin"
    )
    # 关联提交(用于按学生/作业过滤)
    submission: Mapped["Submission"] = relationship(back_populates="_grading_result_rows")


class GradingResultKnowledgePoint(Base):
    """某次批改实际识别的标准知识点事实(level=2 key + raw 语义)。"""

    __tablename__ = "grading_result_knowledge_point"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grading_result_id: Mapped[str] = mapped_column(String(64), ForeignKey("grading_result.grading_result_id"))
    knowledge_point_key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)  # 字典补齐,冗余展示
    raw_name: Mapped[str] = mapped_column(Text)  # 本次实际语义,必须保存
    performance: Mapped[str] = mapped_column(String(16))  # correct/partial/incorrect
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    _grading_result: Mapped["GradingResult"] = relationship(back_populates="_kp_rows")


class GradingResultError(Base):
    """某次批改实际识别的标准错误事实(level=2 code + raw 语义)。"""

    __tablename__ = "grading_result_error"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grading_result_id: Mapped[str] = mapped_column(String(64), ForeignKey("grading_result.grading_result_id"))
    error_code: Mapped[str] = mapped_column(String(64))
    type_name: Mapped[str | None] = mapped_column(String(256), nullable=True)  # 字典补齐
    raw_type: Mapped[str] = mapped_column(Text)  # 本次实际语义
    knowledge_point_key: Mapped[str] = mapped_column(String(128))  # 关联知识点
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    _grading_result: Mapped["GradingResult"] = relationship(back_populates="_error_rows")
