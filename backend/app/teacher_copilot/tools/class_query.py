"""对象发现 Tool(list_class_students / list_class_homeworks)。

只负责发现业务对象(谁在班里/有哪些作业),不计算画像或分析
(参考文档 03 §5.4/5.5、05 §5)。异步实现(Agent 运行时调用)。
"""

from __future__ import annotations

from langchain_core.tools import tool
from sqlalchemy import select

from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.homework import Homework
from app.teacher_copilot.db.models.org import ClassStudent, Student
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.tools.schemas.inputs import ListClassHomeworksInput, ListClassStudentsInput


@tool("list_class_students", args_schema=ListClassStudentsInput)
async def list_class_students(class_id: str) -> dict:
    """查询指定班级的真实学生成员列表(谁在这个班级里)。

    用于全班批量诊断/练习等需要 student_id 集合的任务;不计算学生成绩或掌握度,
    需要长期学情时用 get_class_profile。
    """
    try:
        async with get_session() as session:
            rows = await session.execute(
                select(Student.student_id, Student.name)
                .join(ClassStudent, ClassStudent.student_id == Student.student_id)
                .where(ClassStudent.class_id == class_id)
                .order_by(Student.student_id)
            )
            return ok([{"student_id": sid, "name": name} for sid, name in rows])
    except TcError as e:
        return fail(e)


@tool("list_class_homeworks", args_schema=ListClassHomeworksInput)
async def list_class_homeworks(
    class_id: str, subject: str | None = None,
    start_time: str | None = None, end_time: str | None = None, limit: int = 20,
) -> dict:
    """查询指定班级在某个学科、时间范围内的作业列表(这个时间范围有哪些作业)。

    用于"本周/近期复盘"等发现 homework_id 的任务;不计算完成率或成绩,
    需要某份作业表现时用 get_homework_analysis。
    """
    try:
        async with get_session() as session:
            stmt = select(Homework).where(Homework.class_id == class_id)
            if subject:
                stmt = stmt.where(Homework.subject == subject)
            rows = await session.scalars(
                stmt.order_by(Homework.published_at.desc().nullslast()).limit(limit)
            )
            return ok([{
                "homework_id": h.homework_id, "name": h.name,
                "subject": h.subject,
                "published_at": h.published_at.isoformat() if h.published_at else None,
            } for h in rows])
    except TcError as e:
        return fail(e)
