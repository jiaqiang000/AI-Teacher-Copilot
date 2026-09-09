"""对象发现 Tool(list_class_students / list_class_homeworks)。

只负责发现业务对象(谁在班里/有哪些作业),不计算画像或分析
(参考文档 03 §5.4/5.5、05 §5)。异步实现(Agent 运行时调用)。
"""

from __future__ import annotations

from langchain.tools import tool
from sqlalchemy import select

from app.teacher_copilot.api.identity import get_teacher_id_from_runtime
from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.homework import Homework
from app.teacher_copilot.db.models.org import ClassRoom, ClassStudent, Student
from app.teacher_copilot.errors import TcError
from app.teacher_copilot.services.permission_service import TeacherPermissionService
from app.teacher_copilot.tools.common import parse_iso_time
from app.teacher_copilot.tools.schemas.inputs import (
    ListClassesInput,
    ListClassHomeworksInput,
    ListClassStudentsInput,
)


@tool("list_classes", args_schema=ListClassesInput)
async def list_classes(keyword: str = "") -> dict:
    """按名称关键字查询真实班级列表(谁的名字带这个关键字)。

    教师提到"八三班/三班/某班"等名称时,先调用本工具把班名解析为 class_id,
    再把 class_id 传给 list_class_students / list_class_homeworks / get_class_profile。
    返回为空表示关键字无匹配,此时应请教师确认班级名称。
    """
    try:
        teacher_id = await get_teacher_id_from_runtime(None)
        async with get_session() as session:
            stmt = (
                select(ClassRoom.class_id, ClassRoom.name)
                .where(ClassRoom.teacher_id == teacher_id)
                .order_by(ClassRoom.class_id)
            )
            if keyword:
                stmt = stmt.where(ClassRoom.name.contains(keyword))
            rows = list(await session.execute(stmt))
            return ok([{"class_id": cid, "name": name} for cid, name in rows])
    except TcError as e:
        return fail(e)


@tool("list_class_students", args_schema=ListClassStudentsInput)
async def list_class_students(class_id: str) -> dict:
    """查询指定班级的真实学生成员列表(谁在这个班级里)。

    用于全班批量诊断/练习等需要 student_id 集合的任务;不计算学生成绩或掌握度,
    需要长期学情时用 get_class_profile。
    """
    try:
        teacher_id = await get_teacher_id_from_runtime(None)
        async with TeacherPermissionService() as permissions:
            await permissions.ensure_class_owned(teacher_id, class_id)
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
    class_id: str,
    subject: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 20,
) -> dict:
    """查询指定班级在某个学科、时间范围内的作业列表(这个时间范围有哪些作业)。

    只返回已发布(PUBLISHED)作业,草稿不进入 Agent 视野;时间参数为 ISO 格式
    (如 2026-09-01T00:00:00),按发布时间过滤。
    用于"本周/近期复盘"等发现 homework_id 的任务;不计算完成率或成绩,
    需要某份作业表现时用 get_homework_analysis。
    """
    try:
        teacher_id = await get_teacher_id_from_runtime(None)
        async with TeacherPermissionService() as permissions:
            await permissions.ensure_class_owned(teacher_id, class_id)
        async with get_session() as session:
            stmt = select(Homework).where(
                Homework.class_id == class_id,
                Homework.teacher_id == teacher_id,
                Homework.status == "PUBLISHED",
            )
            if subject:
                stmt = stmt.where(Homework.subject == subject)
            if start_time:
                stmt = stmt.where(
                    Homework.published_at >= parse_iso_time(start_time, "start_time")
                )
            if end_time:
                stmt = stmt.where(
                    Homework.published_at <= parse_iso_time(end_time, "end_time")
                )
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
