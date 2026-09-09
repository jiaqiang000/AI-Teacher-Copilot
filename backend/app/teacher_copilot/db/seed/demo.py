"""演示数据种子:教师/班级/学生/作业/题目。

与参考文档 08 §3.1 评测世界对齐(teacher_01 / class_03 八三班 / 30 名学生),
仅用于开发调试;评测世界的金标准 GradingResult 数据由 evals/ 另行生成。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.homework import Homework, Question
from app.teacher_copilot.db.models.org import ClassRoom, ClassStudent, Student, Teacher

TEACHER_ID = "teacher_01"
CLASS_ID = "class_03"
CLASS_NAME = "八三班"
# 已发布作业必须有 published_at(发布动作写入);固定值保证 seed 可重复执行且结果稳定
HW_004_PUBLISHED_AT = datetime(2026, 9, 1, 8, 0, 0)
EXTRA_CLASSES = (
    ("class_04", "八四班", 100, 32),
    ("class_05", "八五班", 200, 28),
)


async def seed_demo() -> None:
    """写入演示基础数据(幂等)。"""
    async with get_session() as session:
        if await session.scalar(select(Teacher).where(Teacher.teacher_id == TEACHER_ID)) is None:
            session.add(Teacher(teacher_id=TEACHER_ID, name="王老师"))
        if await session.scalar(select(ClassRoom).where(ClassRoom.class_id == CLASS_ID)) is None:
            session.add(ClassRoom(class_id=CLASS_ID, name=CLASS_NAME, teacher_id=TEACHER_ID))
        # 30 名学生(带姓名,供对象解析演示:stu_003 张三,stu_011 李四)
        names = ["张三" if i == 3 else "李四" if i == 11 else f"学生{i:02d}" for i in range(1, 31)]
        for i, name in enumerate(names, start=1):
            sid = f"stu_{i:03d}"
            if await session.scalar(select(Student).where(Student.student_id == sid)) is None:
                session.add(Student(student_id=sid, name=name))
            if await session.scalar(
                select(ClassStudent).where(
                    ClassStudent.class_id == CLASS_ID, ClassStudent.student_id == sid
                )
            ) is None:
                session.add(ClassStudent(class_id=CLASS_ID, student_id=sid))

        # 三班演示入口都必须对应真实组织数据,后续画像/作业事实按班级隔离生成。
        for class_id, class_name, student_offset, student_count in EXTRA_CLASSES:
            if await session.scalar(select(ClassRoom).where(ClassRoom.class_id == class_id)) is None:
                session.add(ClassRoom(
                    class_id=class_id, name=class_name, teacher_id=TEACHER_ID,
                ))
            for index in range(1, student_count + 1):
                sid = f"stu_{student_offset + index:03d}"
                if await session.scalar(select(Student).where(Student.student_id == sid)) is None:
                    session.add(Student(student_id=sid, name=f"{class_name}学生{index:02d}"))
                if await session.scalar(
                    select(ClassStudent).where(
                        ClassStudent.class_id == class_id, ClassStudent.student_id == sid,
                    )
                ) is None:
                    session.add(ClassStudent(class_id=class_id, student_id=sid))
        # 演示作业:hw_004 八年级数学周末作业(3 道题,对应 Figma 示例)
        hw = await session.scalar(select(Homework).where(Homework.homework_id == "hw_004"))
        if hw is None:
            session.add(Homework(
                homework_id="hw_004", name="八年级数学周末作业", class_id=CLASS_ID,
                teacher_id=TEACHER_ID, subject="math", status="PUBLISHED",
                published_at=HW_004_PUBLISHED_AT,
            ))
        elif hw.status == "PUBLISHED" and hw.published_at is None:
            # 修复历史种子写入的"已发布但无发布时间"记录(幂等,可重复执行)
            hw.published_at = HW_004_PUBLISHED_AT
        q_samples = [
            ("q001", 1, "calculation", "easy", "解方程 2x + 4 = 8", 10),
            ("q002", 2, "solution", "medium", "解含括号的一元一次方程", 10),
            ("q003", 3, "solution", "hard", "函数图像综合信息读取", 15),
        ]
        for qid, no, qtype, diff, content, max_score in q_samples:
            if await session.scalar(select(Question).where(Question.question_id == qid)) is None:
                session.add(Question(
                    question_id=qid, homework_id="hw_004", question_no=no,
                    subject="math", question_type=qtype, difficulty=diff,
                    content=content, max_score=max_score,
                ))
        await session.commit()
