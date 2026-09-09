"""Teacher Copilot Tool 层回归测试。

覆盖:
- get_student_grading_history 的过滤参数(知识点/错误码/作业/时间)与证据明细返回
- list_class_homeworks 的草稿排除与发布时间过滤

使用临时 SQLite 数据库,不连接外部 LLM / OCR / OSS。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from app.teacher_copilot.db import models  # noqa: F401  # 确保所有业务表注册
from app.teacher_copilot.db.engine import create_all, dispose_db, get_session, init_db
from app.teacher_copilot.db.models.grading import (
    GradingResult,
    GradingResultError,
    GradingResultKnowledgePoint,
    Submission,
)
from app.teacher_copilot.db.models.homework import Homework
from app.teacher_copilot.db.models.org import Student
from app.teacher_copilot.db.seed.demo import seed_demo
from app.teacher_copilot.tools.class_query import list_class_homeworks
from app.teacher_copilot.tools.profile import get_student_grading_history

TEACHER_ID = "teacher_01"
STUDENT_ID = "stu_003"
OUTSIDER_STUDENT_ID = "stu_no_class"
DRAFT_HOMEWORK_ID = "hw_tools_draft"
RECENT_HOMEWORK_ID = "hw_tools_recent"
OLD_HOMEWORK_ID = "hw_tools_old"
TRANSPOSITION = "math.linear_equation.transposition"


@pytest_asyncio.fixture(scope="module")
async def tool_database(tmp_path_factory: pytest.TempPathFactory):
    """隔离演示库 + 最小批改事实(两次批改命中不同知识点/错误码/时间窗)。"""
    db_path: Path = tmp_path_factory.mktemp("teacher-copilot-tools") / "tc.db"
    await init_db(f"sqlite+aiosqlite:///{db_path}")
    await create_all()
    await seed_demo()

    now = datetime.utcnow()
    recent_at = now - timedelta(days=3)
    old_at = now - timedelta(days=40)

    async with get_session() as session:
        # 无班级归属的学生:验证工具越权拒绝
        session.add(Student(student_id=OUTSIDER_STUDENT_ID, name="班外学生"))
        # 草稿作业:验证 list_class_homeworks 不返回它
        session.add(Homework(
            homework_id=DRAFT_HOMEWORK_ID, name="未发布草稿", class_id="class_03",
            teacher_id=TEACHER_ID, subject="math", status="DRAFT",
        ))
        # 已发布作业:发布时间落在不同时间窗,验证时间过滤
        session.add(Homework(
            homework_id=RECENT_HOMEWORK_ID, name="近期已发布", class_id="class_03",
            teacher_id=TEACHER_ID, subject="math", status="PUBLISHED",
            published_at=now - timedelta(days=2),
        ))
        session.add(Homework(
            homework_id=OLD_HOMEWORK_ID, name="较早已发布", class_id="class_03",
            teacher_id=TEACHER_ID, subject="math", status="PUBLISHED",
            published_at=now - timedelta(days=30),
        ))
        # 两次提交(stu_003 的两道题,满足 UNIQUE(student_id, question_id))
        session.add(Submission(
            submission_id="sub_tools_recent", student_id=STUDENT_ID, question_id="q001",
            homework_id="hw_004", image_url="oss://recent.jpg",
            status="SUCCEEDED", current_stage="COMPLETED",
        ))
        session.add(Submission(
            submission_id="sub_tools_old", student_id=STUDENT_ID, question_id="q002",
            homework_id="hw_004", image_url="oss://old.jpg",
            status="SUCCEEDED", current_stage="COMPLETED",
        ))
        # 近期一次:移项 + SIGN_ERROR
        session.add(GradingResult(
            grading_result_id="gr_tools_recent", submission_id="sub_tools_recent",
            subject="math", question_type="calculation", difficulty="easy",
            score_earned=4.0, score_max=10.0, score_rate=0.4,
            feedback={"summary": "符号错误"}, execution_meta={"route": "math"},
            created_at=recent_at,
        ))
        session.add(GradingResultKnowledgePoint(
            grading_result_id="gr_tools_recent", knowledge_point_key=TRANSPOSITION,
            name="移项", raw_name="移项时符号处理", performance="incorrect",
            evidence="把 +5 移过去没有变号",
        ))
        session.add(GradingResultError(
            grading_result_id="gr_tools_recent", error_code="SIGN_ERROR",
            type_name="符号错误", raw_type="移项未变号",
            knowledge_point_key=TRANSPOSITION, description="移项未变号", evidence="第 2 步",
        ))
        # 更早一次:函数图像,无错误
        session.add(GradingResult(
            grading_result_id="gr_tools_old", submission_id="sub_tools_old",
            subject="math", question_type="solution", difficulty="medium",
            score_earned=9.0, score_max=10.0, score_rate=0.9,
            feedback={"summary": "完成良好"}, execution_meta={"route": "math"},
            created_at=old_at,
        ))
        session.add(GradingResultKnowledgePoint(
            grading_result_id="gr_tools_old",
            knowledge_point_key="math.function.graph",
            name="函数图像", raw_name="读取图像信息", performance="correct",
        ))
        await session.commit()

    yield
    await dispose_db()


@pytest.fixture(autouse=True)
def _fixed_teacher_identity(monkeypatch: pytest.MonkeyPatch):
    """工具在测试进程内固定解析为 teacher_01,不依赖 DeerFlow runtime 登录态。"""
    async def _fake(_runtime: object | None = None) -> str:
        return TEACHER_ID

    monkeypatch.setattr(
        "app.teacher_copilot.tools.profile.get_teacher_id_from_runtime", _fake
    )
    monkeypatch.setattr(
        "app.teacher_copilot.tools.class_query.get_teacher_id_from_runtime", _fake
    )


# ---------- get_student_grading_history ----------

@pytest.mark.asyncio
async def test_history_returns_evidence_details(tool_database):
    """历史事实必须带 performance 与 error 明细,供 Skill 引用证据。"""
    result = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math"}
    )
    assert result["success"] is True
    rows = result["data"]
    assert len(rows) == 2
    # 时间倒序:近期在前
    recent = rows[0]
    assert recent["grading_result_id"] == "gr_tools_recent"
    assert recent["knowledge_points"][0]["knowledge_point_key"] == TRANSPOSITION
    assert recent["knowledge_points"][0]["performance"] == "incorrect"
    assert recent["errors"][0]["error_code"] == "SIGN_ERROR"
    assert recent["errors"][0]["knowledge_point_key"] == TRANSPOSITION
    # 无错误的批改返回空列表而不是缺字段
    assert rows[1]["errors"] == []


@pytest.mark.asyncio
async def test_history_filters_by_knowledge_point(tool_database):
    """knowledge_point_key 必须真正收窄结果集。"""
    result = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math",
         "knowledge_point_key": TRANSPOSITION}
    )
    assert result["success"] is True
    rows = result["data"]
    assert len(rows) == 1
    assert rows[0]["grading_result_id"] == "gr_tools_recent"


@pytest.mark.asyncio
async def test_history_filters_by_error_code(tool_database):
    """error_code 必须真正收窄结果集。"""
    result = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math", "error_code": "SIGN_ERROR"}
    )
    assert result["success"] is True
    rows = result["data"]
    assert len(rows) == 1
    assert rows[0]["grading_result_id"] == "gr_tools_recent"


@pytest.mark.asyncio
async def test_history_filters_by_homework(tool_database):
    """homework_id 必须真正收窄结果集。"""
    matched = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math", "homework_id": "hw_004"}
    )
    assert matched["success"] is True
    assert len(matched["data"]) == 2

    missing = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math", "homework_id": "hw_not_exists"}
    )
    assert missing["success"] is True
    assert missing["data"] == []


@pytest.mark.asyncio
async def test_history_filters_by_time_window(tool_database):
    """start_time / end_time 必须按批改时间收窄。"""
    now = datetime.utcnow()
    boundary = (now - timedelta(days=10)).isoformat()

    recent_only = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math", "start_time": boundary}
    )
    assert [r["grading_result_id"] for r in recent_only["data"]] == ["gr_tools_recent"]

    old_only = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math", "end_time": boundary}
    )
    assert [r["grading_result_id"] for r in old_only["data"]] == ["gr_tools_old"]


@pytest.mark.asyncio
async def test_history_rejects_invalid_time(tool_database):
    """非法时间格式必须是业务错误,不是 500。"""
    result = await get_student_grading_history.ainvoke(
        {"student_id": STUDENT_ID, "subject": "math", "start_time": "不是时间"}
    )
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_history_denies_student_outside_teacher_classes(tool_database):
    """不属于当前教师班级的学生必须拒绝访问。"""
    result = await get_student_grading_history.ainvoke(
        {"student_id": OUTSIDER_STUDENT_ID, "subject": "math"}
    )
    assert result["success"] is False
    assert result["error"]["code"] == "PERMISSION_DENIED"


# ---------- list_class_homeworks ----------

@pytest.mark.asyncio
async def test_list_homeworks_excludes_drafts(tool_database):
    """草稿作业不进入 Agent 视野。"""
    result = await list_class_homeworks.ainvoke({"class_id": "class_03", "subject": "math"})
    assert result["success"] is True
    ids = {row["homework_id"] for row in result["data"]}
    assert DRAFT_HOMEWORK_ID not in ids
    assert {RECENT_HOMEWORK_ID, OLD_HOMEWORK_ID} <= ids


@pytest.mark.asyncio
async def test_list_homeworks_filters_by_publish_time(tool_database):
    """start_time / end_time 必须按发布时间收窄。"""
    now = datetime.utcnow()
    boundary = (now - timedelta(days=10)).isoformat()

    recent_only = await list_class_homeworks.ainvoke(
        {"class_id": "class_03", "subject": "math", "start_time": boundary}
    )
    ids = {row["homework_id"] for row in recent_only["data"]}
    assert RECENT_HOMEWORK_ID in ids
    assert OLD_HOMEWORK_ID not in ids

    old_only = await list_class_homeworks.ainvoke(
        {"class_id": "class_03", "subject": "math", "end_time": boundary}
    )
    ids = {row["homework_id"] for row in old_only["data"]}
    assert OLD_HOMEWORK_ID in ids
    assert RECENT_HOMEWORK_ID not in ids


@pytest.mark.asyncio
async def test_list_homeworks_rejects_invalid_time(tool_database):
    """非法时间格式必须是业务错误,不是 500。"""
    result = await list_class_homeworks.ainvoke(
        {"class_id": "class_03", "start_time": "2026/09/01"}
    )
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"
