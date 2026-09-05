"""Teacher Copilot 巡检缺口的后端回归测试。

测试使用临时 SQLite 数据库，验证三班演示事实真实、稳定且互相区分；
不连接外部 LLM、OCR 或 OSS。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.teacher_copilot.db import models  # noqa: F401  # 确保所有业务表注册
from app.teacher_copilot.db.engine import (
    create_all,
    dispose_db,
    get_session,
    init_db,
)
from app.teacher_copilot.db.models.homework import Homework
from app.teacher_copilot.db.models.org import ClassRoom, ClassStudent
from app.teacher_copilot.db.seed.demo import seed_demo
from app.teacher_copilot.db.seed.seed_v2 import seed_diverse_data, seed_rich_data
from app.teacher_copilot.errors import ClassNotFound
from app.teacher_copilot.services.analysis_service import AnalysisCalculationV1
from app.teacher_copilot.services.homework_service import HomeworkService
from app.teacher_copilot.services.profile_service import ProfileAlgorithmV1


@pytest_asyncio.fixture(scope="module")
async def seeded_database(tmp_path_factory: pytest.TempPathFactory):
    """为本文件建立隔离演示库，避免污染本地运行中的业务数据库。"""
    db_path: Path = tmp_path_factory.mktemp("teacher-copilot") / "tc.db"
    await init_db(f"sqlite+aiosqlite:///{db_path}")
    await create_all()
    await seed_demo()
    await seed_rich_data()
    await seed_diverse_data()
    yield
    await dispose_db()


async def _class_profiles() -> dict[str, dict]:
    """读取三个班级画像，统一作为差异化断言的事实来源。"""
    async with ProfileAlgorithmV1() as algorithm:
        return {
            class_id: await algorithm.compute_class(class_id, "math")
            for class_id in ("class_03", "class_04", "class_05")
        }


@pytest.mark.asyncio
async def test_demo_seed_contains_three_real_classes(seeded_database):
    """三班名称和人数必须来自组织关系，而不是前端固定文案。"""
    async with get_session() as session:
        rows = list(await session.execute(
            select(ClassRoom.class_id, ClassRoom.name)
            .where(ClassRoom.teacher_id == "teacher_01")
            .order_by(ClassRoom.class_id)
        ))
        counts = {}
        for class_id, _ in rows:
            counts[class_id] = await session.scalar(
                select(func.count())
                .select_from(ClassStudent)
                .where(ClassStudent.class_id == class_id)
            )

    assert dict(rows) == {
        "class_03": "八三班",
        "class_04": "八四班",
        "class_05": "八五班",
    }
    assert counts == {"class_03": 30, "class_04": 32, "class_05": 28}


@pytest.mark.asyncio
async def test_demo_class_profiles_are_deterministic_and_materially_different(seeded_database):
    """班级画像要体现高稳、中升、低降三种清晰的教学场景。"""
    profiles = await _class_profiles()
    rates = {
        class_id: profile["overview"]["avg_score_rate"]
        for class_id, profile in profiles.items()
    }
    trends = {
        class_id: profile["overview"]["trend"]
        for class_id, profile in profiles.items()
    }

    assert profiles["class_03"]["basic"]["class_name"] == "八三班"
    assert profiles["class_04"]["basic"]["class_name"] == "八四班"
    assert profiles["class_05"]["basic"]["class_name"] == "八五班"
    assert trends == {
        "class_03": "stable",
        "class_04": "improving",
        "class_05": "declining",
    }
    assert min(rates.values()) is not None
    assert max(rates.values()) - min(rates.values()) >= 0.20

    weak_keys = {
        class_id: {item["knowledge_point_key"] for item in profile["weak_points"]}
        for class_id, profile in profiles.items()
    }
    assert any("combine_like_terms" in key for key in weak_keys["class_04"])
    assert any("graph" in key or "application" in key for key in weak_keys["class_05"])
    assert len({frozenset(keys) for keys in weak_keys.values()}) == 3

    attention_counts = {
        class_id: len(profile["attention_students"])
        for class_id, profile in profiles.items()
    }
    assert attention_counts["class_03"] < attention_counts["class_04"] < attention_counts["class_05"]


@pytest.mark.asyncio
async def test_demo_homeworks_have_distinct_completion_profiles(seeded_database):
    """每班作业也要有自己的完成表现，不能只差一个班级名称。"""
    async with HomeworkService() as service:
        homeworks = await service.list_homeworks("teacher_01")

    by_class: dict[str, list[Homework]] = {"class_03": [], "class_04": [], "class_05": []}
    for homework in homeworks:
        by_class[homework.class_id].append(homework)

    assert all(len(items) >= 4 for items in by_class.values())
    completion_rates = {}
    for class_id, items in by_class.items():
        latest = max(items, key=lambda item: item.published_at or item.created_at)
        async with AnalysisCalculationV1() as algorithm:
            analysis = await algorithm.compute_homework_analysis(latest.homework_id, class_id)
        completion_rates[class_id] = analysis["completion"]["completion_rate"]

    assert completion_rates["class_03"] > completion_rates["class_04"] > completion_rates["class_05"]
    assert len(set(completion_rates.values())) == 3


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
async def test_rich_demo_seed_is_idempotent(seeded_database):
    """重复初始化不会重复插入学生、作业、题目或批改事实。"""
    async with get_session() as session:
        before = {
            "classes": await session.scalar(select(func.count()).select_from(ClassRoom)),
            "homeworks": await session.scalar(select(func.count()).select_from(Homework)),
        }

    await seed_demo()
    await seed_rich_data()

    async with get_session() as session:
        after = {
            "classes": await session.scalar(select(func.count()).select_from(ClassRoom)),
            "homeworks": await session.scalar(select(func.count()).select_from(Homework)),
        }

    assert after == before
