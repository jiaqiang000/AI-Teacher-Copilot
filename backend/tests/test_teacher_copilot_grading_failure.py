"""Teacher Copilot 批改失败路径测试(008 FR-002;SC-001/SC-002/SC-004)。

覆盖三件事:

1. 未配置密钥时模型与识别客户端抛专用错误,不再返回可被下游解析的占位结果;
2. 校验层拒绝"必需字段缺失或类型不对"的诊断(占位输出的形态),但放行合法的空数组;
3. 未配置密钥时跑一次真实批改主流程 → 提交显式 FAILED,且批改结果表无新增行。

不访问外部 LLM / OCR / OSS:通过清空 ``TC_LLM_API_KEY`` 与 ``TC_OCR_API_KEY``
模拟"未配置",并预置一条 OcrResult 走批改流程的"幂等复用"分支,使流程能推进
到模型调用那一步,从而验证模型侧的显式失败。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.teacher_copilot.config import settings
from app.teacher_copilot.db import models  # noqa: F401  # 确保所有业务表注册
from app.teacher_copilot.db.engine import create_all, dispose_db, get_session, init_db
from app.teacher_copilot.db.models.grading import GradingResult, OcrResult, Submission
from app.teacher_copilot.db.models.homework import Question
from app.teacher_copilot.errors import (
    GradingOutputInvalid,
    InvalidArgument,
    ModelNotConfigured,
    OcrNotConfigured,
)
from app.teacher_copilot.grading.assembler import GradingResultAssembler
from app.teacher_copilot.grading.validators.taxonomy_validator import TaxonomyValidator
from app.teacher_copilot.grading.workflow import _persist_ocr, run_grading_workflow
from app.teacher_copilot.models.clients.llm import LlmClient
from app.teacher_copilot.models.clients.ocr import OcrClient
from app.teacher_copilot.services.question_service import QuestionService
from app.teacher_copilot.services.submission_service import SubmissionService

SUBMISSION_ID = "sub_failpath_001"
QUESTION_ID = "q_failpath_001"
HOMEWORK_ID = "hw_failpath"
# 识别结果为空(没有任何 Block)的提交:应显式失败而不是拿空作答批改
EMPTY_OCR_SUBMISSION_ID = "sub_failpath_empty_ocr"
# 仅用于直接验证 _persist_ocr 状态判定,不预置 OcrResult
PERSIST_SUBMISSION_ID = "sub_failpath_persist"


@pytest.fixture()
def no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟"密钥未配置"环境。

    ``get_config()`` 是模块级单例,清掉环境变量后必须一并重置单例,
    否则本机 ``backend/.env`` 已加载的密钥会被读回,测试将变成真实外部调用。
    """
    monkeypatch.delenv("TC_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TC_OCR_API_KEY", raising=False)
    monkeypatch.setattr(settings, "_config", None)


@pytest_asyncio.fixture(scope="module")
async def grading_database(tmp_path_factory: pytest.TempPathFactory):
    """建立隔离数据库,并准备一条"已识别、待批改"的提交。

    预置 OcrResult 是为了走 workflow 的"幂等复用"分支(已有识别结果则跳过 OCR),
    这样即使未配置 OCR 密钥,流程也能推进到模型调用。
    """
    db_path: Path = tmp_path_factory.mktemp("teacher-copilot-failure") / "tc.db"
    # 先释放可能残留的全局引擎,确保本文件拿到的是自己的库
    await dispose_db()
    await init_db(f"sqlite+aiosqlite:///{db_path}")
    await create_all()

    async with get_session() as session:
        session.add(Question(
            question_id=QUESTION_ID, homework_id=HOMEWORK_ID, question_no=1,
            subject="math", question_type="calculation", difficulty="easy",
            content="解方程 2x + 4 = 8", max_score=10,
        ))
        session.add(Submission(
            submission_id=SUBMISSION_ID, student_id="stu_failpath",
            question_id=QUESTION_ID, homework_id=HOMEWORK_ID,
            image_url="https://example.com/answer.png",
            status="PENDING", current_stage="QUEUED",
        ))
        session.add(OcrResult(
            ocr_result_id=f"ocr_{SUBMISSION_ID}", submission_id=SUBMISSION_ID,
            model="glm-ocr", status="SUCCEEDED", md_results="$$ x = 2 $$",
            layout_details=[{
                "index": 1, "label": "formula", "content": "$$ 2x + 4 = 8 $$",
                "bbox2d": [0, 0, 100, 40], "width": 100, "height": 600,
            }],
        ))
        # 识别结果为空(没有任何 Block)的提交:用于验证"空识别不得继续批改"
        session.add(Submission(
            submission_id=EMPTY_OCR_SUBMISSION_ID, student_id="stu_failpath_empty",
            question_id=QUESTION_ID, homework_id=HOMEWORK_ID,
            image_url="https://example.com/blank.png",
            status="PENDING", current_stage="QUEUED",
        ))
        session.add(OcrResult(
            ocr_result_id=f"ocr_{EMPTY_OCR_SUBMISSION_ID}",
            submission_id=EMPTY_OCR_SUBMISSION_ID,
            model="glm-ocr", status="SUCCEEDED", md_results="", layout_details=[],
        ))
        # 不预置 OcrResult:留给 _persist_ocr 状态判定用例直接调用
        session.add(Submission(
            submission_id=PERSIST_SUBMISSION_ID, student_id="stu_failpath_persist",
            question_id=QUESTION_ID, homework_id=HOMEWORK_ID,
            image_url="https://example.com/persist.png",
            status="PENDING", current_stage="QUEUED",
        ))
        await session.commit()

    yield
    await dispose_db()


@pytest.mark.asyncio
async def test_llm_without_key_raises_model_not_configured(no_api_keys):
    """无密钥时模型调用以专用错误显式失败,不返回占位 JSON(FR-001)。"""
    with pytest.raises(ModelNotConfigured) as exc:
        await LlmClient().generate(prompt="解方程 2x + 4 = 8")

    assert exc.value.code == "MODEL_NOT_CONFIGURED"
    assert "TC_LLM_API_KEY" in exc.value.message


@pytest.mark.asyncio
async def test_ocr_without_key_raises_ocr_not_configured(no_api_keys):
    """无密钥时识别以专用错误显式失败,不返回硬编码识别文本(FR-004)。"""
    with pytest.raises(OcrNotConfigured) as exc:
        await OcrClient().recognize("answer.png")

    assert exc.value.code == "OCR_NOT_CONFIGURED"
    assert "TC_OCR_API_KEY" in exc.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("diagnosis", "expected_fragment"),
    [
        # 占位输出的形态:两个必需键都不存在
        ({"_mock": True}, "knowledge_points"),
        # 只缺一个键
        ({"knowledge_points": []}, "errors"),
        # 键在但类型不对
        ({"knowledge_points": "x", "errors": []}, "必须是数组"),
        # 条目自身缺标识字段
        ({"knowledge_points": [{"performance": "correct"}], "errors": []}, "key"),
        # 诊断根本不是对象
        (None, "必须是对象"),
    ],
)
async def test_validator_rejects_incomplete_diagnosis(
    grading_database, diagnosis, expected_fragment
):
    """结构不完整的诊断必须判为不合格,而不是取空值放行(FR-002、SC-002)。"""
    async with TaxonomyValidator() as validator:
        with pytest.raises(GradingOutputInvalid) as exc:
            await validator.validate_diagnosis("math", diagnosis)

    assert expected_fragment in exc.value.message


@pytest.mark.asyncio
async def test_validator_allows_present_but_empty_lists(grading_database):
    """两个键都在且为数组时放行:空数组合法(全对答案可以没有错误)。

    这是 008 方案 A 的边界——拦"字段缺失",不拦"合法的空列表"。
    """
    async with TaxonomyValidator() as validator:
        cleaned = await validator.validate_diagnosis(
            "math", {"knowledge_points": [], "errors": []}
        )

    assert cleaned == {"knowledge_points": [], "errors": []}


def test_assembler_does_not_fill_default_empty_diagnosis():
    """组装器不得为"模型漏给 diagnosis"补默认空诊断(FR-002)。

    简化结构归一分支会自行构造 diagnosis(两个键都在,空数组合法);
    但标准结构下模型漏给 diagnosis 时必须保持缺失——补成空诊断会让
    校验层把它误判为"学生没有任何知识点问题、也没有任何错误"。

    注:feedback 自 008 T040 起是必需输出,故这里显式给出,
    以便把"diagnosis 缺失"这一条单独观察出来。
    """
    assembled = GradingResultAssembler.assemble_math(
        {
            "steps": [{
                "step_index": 1, "description": "整题作答",
                "evidence_block_ids": [], "error_block_ids": [],
                "status": "correct", "earned_score": 10, "max_score": 10,
            }],
            "score": {"earned": 10, "max": 10},
            "feedback": {"summary": "解题正确"},
        },
        "math", "calculation", "easy",
    )

    assert assembled["diagnosis"] is None


@pytest.mark.asyncio
async def test_grading_workflow_fails_explicitly_without_key_and_writes_no_result(
    grading_database, no_api_keys
):
    """无密钥触发批改:提交显式 FAILED、错误码可区分,且批改结果表无新增行。

    对应 SC-001 与 SC-004:失败信息来自后端记录而非占位内容;
    同时验证占位/降级结果没有落进业务数据表(FR-002)。
    """
    await run_grading_workflow(SUBMISSION_ID)

    async with SubmissionService() as service:
        submission = await service.get(SUBMISSION_ID)
    async with get_session() as session:
        result_rows = await session.scalar(
            select(func.count()).select_from(GradingResult).where(
                GradingResult.submission_id == SUBMISSION_ID
            )
        )

    assert submission.status == "FAILED"
    assert submission.error_code == "MODEL_NOT_CONFIGURED"
    assert submission.error_message  # 失败信息本身要落库,供前端展示(FR-004a)
    assert result_rows == 0


# ---------------------------------------------------------------- feedback 必需(T040)


def _math_output(**overrides) -> dict:
    """构造一份可通过数学契约校验的输出,便于逐项破坏。"""
    base = {
        "steps": [{
            "step_index": 1, "description": "整题作答", "evidence_block_ids": [],
            "error_block_ids": [], "status": "correct",
            "earned_score": 10, "max_score": 10, "feedback": "列式与计算均正确",
        }],
        "score": {"earned": 10, "max": 10},
        "diagnosis": {"knowledge_points": [], "errors": []},
        "feedback": {"summary": "解题正确", "strengths": ["步骤完整"], "improvements": []},
    }
    base.update(overrides)
    return base


def test_assembler_requires_feedback_summary_for_math():
    """feedback 是必需输出:缺失或空白一律判不合格,不再兜底成空评语(008 T040)。

    在此之前的实现用 ``output.get("feedback", {"summary": ""})`` 兜底,把
    "模型没给评语"伪装成"这道题没什么可说的"——教师端因此永远看不到数学评语。
    """
    assembled = GradingResultAssembler.assemble_math(
        _math_output(), "math", "calculation", "easy"
    )
    assert assembled["feedback"] == {
        "summary": "解题正确", "strengths": ["步骤完整"], "improvements": [],
    }

    broken_cases = {
        "缺 feedback 键": {k: v for k, v in _math_output().items() if k != "feedback"},
        "summary 全空白": _math_output(feedback={"summary": "   "}),
        "summary 非字符串": _math_output(feedback={"summary": None}),
        "feedback 不是对象": _math_output(feedback="写得好"),
    }
    for broken in broken_cases.values():
        with pytest.raises(GradingOutputInvalid):
            GradingResultAssembler.assemble_math(
                broken, "math", "calculation", "easy"
            )


def test_assembler_simplified_math_needs_feedback_too():
    """简化结构归一分支不能绕过 feedback 必需校验(008 T040)。"""
    simplified = {
        "score": 10, "max_score": 10, "is_correct": True,
        "feedback": {"summary": "全对"},
    }
    assembled = GradingResultAssembler.assemble_math(
        simplified, "math", "calculation", "easy"
    )
    assert assembled["feedback"]["summary"] == "全对"

    with pytest.raises(GradingOutputInvalid):
        GradingResultAssembler.assemble_math(
            {"score": 10, "max_score": 10, "is_correct": True},
            "math", "calculation", "easy",
        )


def test_assembler_requires_feedback_summary_for_english():
    """英语侧同一口径(008 T040)。"""
    dims = ("content", "organization", "grammar", "vocabulary")
    base = {
        "english_essay_detail": {
            "dimension_scores": {d: {"score": 4, "max_score": 5} for d in dims},
            "evidence": {d: ["证据"] for d in dims},
        },
    }
    assembled = GradingResultAssembler.assemble_english(
        {**base, "feedback": {"summary": "整体不错"}}, "english", "essay"
    )
    assert assembled["feedback"]["summary"] == "整体不错"

    with pytest.raises(GradingOutputInvalid):
        GradingResultAssembler.assemble_english(base, "english", "essay")


# ---------------------------------------------------------------- 空识别不得继续(T041)


@pytest.mark.asyncio
async def test_persist_ocr_does_not_mark_empty_result_as_succeeded(grading_database):
    """识别结果为空时证据状态不得写成 SUCCEEDED(008 T041)。

    否则"识别失败"在证据表里看起来就是"识别成功"。
    """
    await _persist_ocr(PERSIST_SUBMISSION_ID, {"md_results": "", "layout_details": []})

    async with get_session() as session:
        status = await session.scalar(
            select(OcrResult.status).where(
                OcrResult.submission_id == PERSIST_SUBMISSION_ID
            )
        )

    assert status == "EMPTY"


@pytest.mark.asyncio
async def test_empty_ocr_result_fails_instead_of_grading_nothing(
    grading_database, no_api_keys
):
    """空识别必须显式失败:不得拿空作答产出一个"看似正常"的分数(008 T041)。"""
    await run_grading_workflow(EMPTY_OCR_SUBMISSION_ID)

    async with SubmissionService() as service:
        submission = await service.get(EMPTY_OCR_SUBMISSION_ID)
    async with get_session() as session:
        result_rows = await session.scalar(
            select(func.count()).select_from(GradingResult).where(
                GradingResult.submission_id == EMPTY_OCR_SUBMISSION_ID
            )
        )

    assert submission.status == "FAILED"
    assert submission.error_code == "OCR_EMPTY_RESULT"
    assert submission.error_message
    assert result_rows == 0


# ---------------------------------------------------------------- 满分必须为正(T042)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_max_score", [0, -5])
async def test_create_question_rejects_non_positive_max_score(
    grading_database, bad_max_score
):
    """数学满分必须为正:0/负数会让得分率兜底成 0,把班级均分一起拉低(008 T042)。"""
    async with QuestionService() as service:
        with pytest.raises(InvalidArgument) as exc:
            await service.create_question(
                question_id=f"q_bad_max_{bad_max_score}",
                homework_id=HOMEWORK_ID, subject="math",
                question_type="calculation", content="解方程 2x = 4",
                max_score=bad_max_score, difficulty="easy",
            )

    assert "满分" in exc.value.message
