"""基础组织 ORM:teacher / student / class / class_student。

字段依据 data-model.md §2.1;主键为字符串 *_id 前缀样式(如 teacher_01)。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.teacher_copilot.db.engine import Base


class Teacher(Base):
    """教师账号。"""

    __tablename__ = "teacher"

    teacher_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Student(Base):
    """学生账号。"""

    __tablename__ = "student"

    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ClassRoom(Base):
    """班级(Class 为 Python 关键字,故改名 ClassRoom;表名保持 class)。"""

    __tablename__ = "class"

    class_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    teacher_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ClassStudent(Base):
    """班级-学生归属关系(多对多)。"""

    __tablename__ = "class_student"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_class_student"),)

    class_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
