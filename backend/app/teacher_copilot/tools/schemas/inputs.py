"""Tool 输入 Schema(pydantic)。

按 contracts/teacher-agent-contracts.md 定义 8 个 Tool 的输入;
Tool 名称、字段语义与参考文档 docs/05-tool-skill.md §6 一致。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# 学科/难度/题型枚举
Subject = Literal["math", "english"]
Difficulty = Literal["easy", "medium", "hard"]
QuestionType = Literal["calculation", "solution", "essay"]


class GetStudentProfileInput(BaseModel):
    """学生画像输入。"""
    student_id: str = Field(description="学生唯一 ID")
    subject: Subject = Field(description="学科,math/english")
    sections: list[Literal["overview", "knowledge_points", "weak_points",
                           "recurring_errors", "difficulty_performance"]] | None = Field(
        default=None, description="返回模块;为空返回完整画像"
    )


class GetStudentGradingHistoryInput(BaseModel):
    """学生批改历史输入。"""
    student_id: str = Field(description="学生唯一 ID")
    subject: Subject | None = Field(default=None, description="学科过滤")
    knowledge_point_key: str | None = Field(default=None, description="标准二级知识点")
    error_code: str | None = Field(default=None, description="标准二级错误类型")
    homework_id: str | None = Field(default=None, description="作业过滤")
    start_time: str | None = Field(default=None, description="开始时间(ISO)")
    end_time: str | None = Field(default=None, description="结束时间(ISO)")
    limit: int = Field(default=20, description="返回数量")


class GetClassProfileInput(BaseModel):
    """班级画像输入。"""
    class_id: str = Field(description="班级唯一 ID")
    subject: Subject = Field(description="学科")
    sections: list[Literal["overview", "knowledge_points", "weak_points",
                           "common_errors", "attention_students"]] | None = Field(
        default=None, description="返回模块;为空返回完整画像"
    )


class ListClassStudentsInput(BaseModel):
    """班级学生列表输入。"""
    class_id: str = Field(description="班级唯一 ID")


class ListClassHomeworksInput(BaseModel):
    """班级作业列表输入。"""
    class_id: str = Field(description="班级唯一 ID")
    subject: Subject | None = Field(default=None, description="学科过滤")
    start_time: str | None = Field(default=None, description="开始时间(ISO)")
    end_time: str | None = Field(default=None, description="结束时间(ISO)")
    limit: int = Field(default=20, description="返回数量")


class GetHomeworkAnalysisInput(BaseModel):
    """作业分析输入。"""
    homework_id: str = Field(description="作业唯一 ID")
    class_id: str = Field(description="班级唯一 ID")
    sections: list[Literal["completion", "performance", "knowledge_points",
                           "questions", "attention_students"]] | None = Field(
        default=None, description="返回模块;为空返回完整分析"
    )


class GetQuestionAnalysisInput(BaseModel):
    """题目分析输入。"""
    homework_id: str = Field(description="作业唯一 ID")
    class_id: str = Field(description="班级唯一 ID")
    question_id: str = Field(description="题目唯一 ID")


class SearchQuestionBankInput(BaseModel):
    """题库检索输入。"""
    subject: Subject = Field(description="学科")
    knowledge_point_keys: list[str] = Field(description="标准二级知识点标识(至少命中一个)")
    difficulty: Difficulty | None = Field(default=None, description="难度")
    question_type: QuestionType | None = Field(default=None, description="题型")
    grade: str | None = Field(default=None, description="年级")
    count: int = Field(default=10, description="返回数量")
    exclude_question_bank_item_ids: list[str] | None = Field(default=None, description="排除题库题 ID")
