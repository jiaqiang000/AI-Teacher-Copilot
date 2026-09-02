"""作业/题目/题库 ORM:homework / question / question_bank_item / 关联表。

字段依据 data-model.md §2.2/§2.6;homework 状态 DRAFT/PUBLISHED,
deadline 为可选截止时间(仅展示,不做逾期拦截)。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.teacher_copilot.db.engine import Base


class Homework(Base):
    """一次作业(先草稿,发布后学生可见)。"""

    __tablename__ = "homework"

    homework_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    class_id: Mapped[str] = mapped_column(String(64))
    teacher_id: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(16))  # math / english
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")  # DRAFT / PUBLISHED
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 可选截止时间:仅用于学生端展示与"待批改作业数(今天截止)"统计,不做逾期拦截
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Question(Base):
    """某个 Homework 中真正布置出去的一道题。"""

    __tablename__ = "question"
    __table_args__ = (
        UniqueConstraint("homework_id", "question_no", name="uq_question_no_in_homework"),
    )

    question_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    homework_id: Mapped[str] = mapped_column(String(64))
    question_no: Mapped[int] = mapped_column()  # 作业内展示序号,唯一
    subject: Mapped[str] = mapped_column(String(16))  # 继承 homework.subject
    question_type: Mapped[str] = mapped_column(String(32))  # calculation/solution/essay
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)  # easy/medium/hard
    content: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 题目原图(可选)
    max_score: Mapped[int] = mapped_column()  # 数学教师填;英语作文固定 20
    # 来源题库题 ID,仅追踪来源,不建立实时引用关系
    source_question_bank_item_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )


class QuestionBankItem(Base):
    """系统题库中的可复用题目资源(独立于 homework.question)。"""

    __tablename__ = "question_bank_item"

    question_bank_item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(16))
    grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    question_type: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class QuestionBankItemKnowledgePoint(Base):
    """题库题 ↔ 标准知识点(level=2)关联。"""

    __tablename__ = "question_bank_item_knowledge_point"
    __table_args__ = (
        UniqueConstraint(
            "question_bank_item_id", "knowledge_point_key",
            name="uq_qb_item_knowledge_point",
        ),
    )

    question_bank_item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_point_key: Mapped[str] = mapped_column(String(128), primary_key=True)
