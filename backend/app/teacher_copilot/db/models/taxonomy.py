"""标准分类字典 ORM:knowledge_point / error_type(两级 Taxonomy)。

字段依据 data-model.md §2.5;level=1 为大类,level=2 为可落库小类,
每个大类至少一个 is_other=True 的兜底小类。
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.teacher_copilot.db.engine import Base


class KnowledgePoint(Base):
    """标准知识点分类(两级)。"""

    __tablename__ = "knowledge_point"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)  # 如 math.linear_equation.transposition
    name: Mapped[str] = mapped_column(String(256))  # 标准展示名称
    subject: Mapped[str] = mapped_column(String(16))  # math / english
    parent_key: Mapped[str | None] = mapped_column(String(128), nullable=True)  # level=2 指向大类
    level: Mapped[int] = mapped_column()  # 1 / 2
    is_other: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否为该大类 OTHER 兜底


class ErrorType(Base):
    """标准错误类型分类(两级)。"""

    __tablename__ = "error_type"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)  # 如 SIGN_ERROR
    name: Mapped[str] = mapped_column(String(256))  # 标准展示名称
    subject: Mapped[str] = mapped_column(String(16))
    parent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[int] = mapped_column()  # 1 / 2
    is_other: Mapped[bool] = mapped_column(Boolean, default=False)
