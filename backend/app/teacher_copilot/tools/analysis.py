"""分析 Tool(get_homework_analysis / get_question_analysis)。

直接返回 AnalysisCalculationV1 的确定性计算结果,不重新计算统计字段
(参考文档 03 §5.6/5.7、05 §1.3)。异步实现(Agent 运行时调用)。
"""

from __future__ import annotations

from langchain.tools import tool

from app.teacher_copilot.api.identity import get_teacher_id_from_runtime
from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.errors import PermissionDenied, QuestionNotFound, TcError
from app.teacher_copilot.services.analysis_service import AnalysisCalculationV1
from app.teacher_copilot.services.permission_service import TeacherPermissionService
from app.teacher_copilot.tools.schemas.inputs import (
    GetHomeworkAnalysisInput,
    GetQuestionAnalysisInput,
)


@tool("get_homework_analysis", args_schema=GetHomeworkAnalysisInput)
async def get_homework_analysis(
    homework_id: str,
    class_id: str,
    sections: list[str] | None = None,
) -> dict:
    """分析某个班级的一次具体作业(完成情况/成绩表现/知识点/题目表现/重点关注学生)。

    用于回答"这次作业完成率、题目表现如何";不用于枚举作业列表
    (那是 list_class_homeworks)。
    """
    try:
        teacher_id = await get_teacher_id_from_runtime(None)
        async with TeacherPermissionService() as permissions:
            await permissions.ensure_class_owned(teacher_id, class_id)
            homework = await permissions.ensure_homework_owned(teacher_id, homework_id)
        if homework.class_id != class_id:
            raise PermissionDenied(f"无权以班级 {class_id} 访问作业 {homework_id}")
        async with AnalysisCalculationV1() as algo:
            data = await algo.compute_homework_analysis(homework_id, class_id)
        if sections:
            data = {k: data[k] for k in sections if k in data}
        return ok(data)
    except TcError as e:
        return fail(e)


@tool("get_question_analysis", args_schema=GetQuestionAnalysisInput)
async def get_question_analysis(
    homework_id: str,
    class_id: str,
    question_id: str,
) -> dict:
    """下钻分析某次作业中的一道具体题(作答人数/平均得分率/错误率/常见错误/典型证据)。

    用于回答"第 8 题错误率/错在哪里";需先获取作业的题目表现
    (get_homework_analysis)再下钻。
    """
    try:
        teacher_id = await get_teacher_id_from_runtime(None)
        async with TeacherPermissionService() as permissions:
            await permissions.ensure_class_owned(teacher_id, class_id)
            homework = await permissions.ensure_homework_owned(teacher_id, homework_id)
            question = await permissions.ensure_question_owned(teacher_id, question_id)
        if homework.class_id != class_id or question.homework_id != homework_id:
            raise PermissionDenied(f"无权访问题目 {question_id}")
        async with AnalysisCalculationV1() as algo:
            full = await algo.compute_homework_analysis(homework_id, class_id)
        qs = next((q for q in full["questions"] if q["question_id"] == question_id), None)
        if qs is None:
            return fail(QuestionNotFound(f"题目 {question_id} 无有效作答数据"))
        return ok(qs)
    except TcError as e:
        return fail(e)
