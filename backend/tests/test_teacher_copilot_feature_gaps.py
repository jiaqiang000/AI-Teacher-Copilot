"""Teacher Copilot 巡检缺口的后端回归测试。

测试使用临时 SQLite 数据库，验证作业范围、提交关系和题目分析边界；
不连接外部 LLM、OCR 或 OSS。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select

from app.teacher_copilot.api.routers.profile import question_analysis
from app.teacher_copilot.db import models  # noqa: F401  # 确保所有业务表注册
from app.teacher_copilot.db.engine import (
    create_all,
    dispose_db,
    get_session,
    init_db,
)
from app.teacher_copilot.db.models.homework import Homework
from app.teacher_copilot.db.models.org import ClassRoom
from app.teacher_copilot.db.seed.demo import seed_demo
from app.teacher_copilot.errors import ClassNotFound, InvalidArgument, QuestionNotFound
from app.teacher_copilot.services.analysis_service import AnalysisCalculationV1
from app.teacher_copilot.services.homework_service import HomeworkService
from app.teacher_copilot.services.profile_service import ProfileAlgorithmV1
from app.teacher_copilot.services.question_service import QuestionService
from app.teacher_copilot.services.submission_service import SubmissionService


@pytest_asyncio.fixture(scope="module")
async def seeded_database(tmp_path_factory: pytest.TempPathFactory):
    """为本文件建立隔离演示库，避免污染本地运行中的业务数据库。"""
    db_path: Path = tmp_path_factory.mktemp("teacher-copilot") / "tc.db"
    await init_db(f"sqlite+aiosqlite:///{db_path}")
    await create_all()
    await seed_demo()
    # 仅建立范围过滤测试所需的最小作业，不生成多周演示历史。
    async with HomeworkService() as service:
        await service.create_homework(
            homework_id="hw_scope_fixture", name="范围过滤测试",
            class_id="class_04", teacher_id="teacher_01", subject="math",
        )
    yield
    await dispose_db()


@pytest.mark.asyncio
async def test_homework_list_is_scoped_by_teacher_and_class(seeded_database):
    """作业管理接口的查询基础必须遵守教师和班级过滤条件。"""
    async with HomeworkService() as service:
        class_04 = await service.list_homeworks(
            "teacher_01", class_id="class_04", subject="math"
        )
        other_teacher = await service.list_homeworks("teacher_missing")

    assert class_04
    assert {homework.class_id for homework in class_04} == {"class_04"}
    assert {homework.teacher_id for homework in class_04} == {"teacher_01"}
    assert other_teacher == []


@pytest.mark.asyncio
async def test_invalid_class_does_not_fall_back_to_class_03(seeded_database):
    """无效班级 ID 必须明确报错,不能返回八三班画像。"""
    with pytest.raises(ClassNotFound):
        async with ProfileAlgorithmV1() as algorithm:
            await algorithm.compute_class("class_missing", "math")


@pytest.mark.asyncio
async def test_submission_rejects_question_homework_mismatch_without_resetting(seeded_database):
    """题目和作业必须是同一条关系,非法请求不能创建或重置提交。"""
    async with HomeworkService() as service:
        valid_homework = await service.create_homework(
            homework_id="hw_test_submission",
            name="提交关系校验作业",
            class_id="class_03",
            teacher_id="teacher_01",
            subject="math",
        )
        other_homework = await service.create_homework(
            homework_id="hw_test_submission_other",
            name="提交关系校验另一份作业",
            class_id="class_03",
            teacher_id="teacher_01",
            subject="math",
        )
    async with QuestionService() as service:
        valid_question = await service.create_question(
            question_id="q_test_submission",
            homework_id=valid_homework.homework_id,
            subject="math",
            question_type="calculation",
            content="计算 1 + 1",
            max_score=10,
            difficulty="easy",
        )
        other_question = await service.create_question(
            question_id="q_test_submission_other",
            homework_id=other_homework.homework_id,
            subject="math",
            question_type="calculation",
            content="计算 2 + 2",
            max_score=10,
            difficulty="easy",
        )

    async with SubmissionService() as service:
        submission, created = await service.submit(
            student_id="stu_003",
            question_id=valid_question.question_id,
            homework_id=valid_homework.homework_id,
            image_url="https://example.com/valid.png",
        )
        with pytest.raises(InvalidArgument):
            await service.submit(
                student_id="stu_003",
                question_id=other_question.question_id,
                homework_id=valid_homework.homework_id,
                image_url="https://example.com/wrong.png",
            )
        with pytest.raises(QuestionNotFound):
            await service.submit(
                student_id="stu_003",
                question_id="q_missing_submission",
                homework_id=valid_homework.homework_id,
                image_url="https://example.com/missing.png",
            )
        unchanged = await service.get(submission.submission_id)

    assert created is True
    assert unchanged.image_url == "https://example.com/valid.png"
    assert unchanged.status == "PENDING"


@pytest.mark.asyncio
async def test_question_analysis_rejects_cross_class_scope_and_empty_data(seeded_database):
    """题目分析必须绑定题目、作业、班级和教师,空作答不能伪造统计。"""
    with pytest.raises(HTTPException) as cross_class:
        await question_analysis(
            question_id="q001",
            homework_id="hw_004",
            class_id="class_04",
            teacher_id="teacher_01",
        )

    async with HomeworkService() as service:
        await service.create_homework(
            homework_id="hw_test_analysis_empty",
            name="无有效作答分析作业",
            class_id="class_03",
            teacher_id="teacher_01",
            subject="math",
        )
    async with QuestionService() as service:
        await service.create_question(
            question_id="q_test_analysis_empty",
            homework_id="hw_test_analysis_empty",
            subject="math",
            question_type="calculation",
            content="计算 3 + 3",
            max_score=10,
            difficulty="easy",
        )

    with pytest.raises(HTTPException) as empty_data:
        await question_analysis(
            question_id="q_test_analysis_empty",
            homework_id="hw_test_analysis_empty",
            class_id="class_03",
            teacher_id="teacher_01",
        )

    assert cross_class.value.status_code == 400
    assert empty_data.value.status_code == 404


@pytest.mark.asyncio
async def test_base_demo_seed_is_idempotent(seeded_database):
    """重复初始化不会重复插入学生、作业、题目或批改事实。"""
    async with get_session() as session:
        before = {
            "classes": await session.scalar(select(func.count()).select_from(ClassRoom)),
            "homeworks": await session.scalar(select(func.count()).select_from(Homework)),
        }

    await seed_demo()

    async with get_session() as session:
        after = {
            "classes": await session.scalar(select(func.count()).select_from(ClassRoom)),
            "homeworks": await session.scalar(select(func.count()).select_from(Homework)),
        }

    assert after == before
