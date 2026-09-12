"""Grading Workflow 主流程(参考文档 01 §5 / contracts/grading-api.md)。

阶段推进:QUEUED→OCR→PARSING→GRADING→ASSEMBLING_RESULT→COMPLETED,
每阶段更新 Submission.status/current_stage 并发布 grading.* 事件。
数学读取 Question.difficulty 路由;数学由题目属性确定,不再重复识别难度。

日志(宪法 X):每阶段开始/结束输出日志与耗时,便于监控与排查。
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import GradingResult, GradingResultError, GradingResultKnowledgePoint, OcrResult
from app.teacher_copilot.db.models.homework import Question
from app.teacher_copilot.grading.assembler import GradingResultAssembler
from app.teacher_copilot.grading.english_grading import run_english_grading
from app.teacher_copilot.grading.math_grading import run_math_grading
from app.teacher_copilot.grading.stream_adapter import publish_grading_event

logger = logging.getLogger("teacher_copilot.grading")
from app.teacher_copilot.grading.validators.taxonomy_validator import TaxonomyValidator
from app.teacher_copilot.models.clients.llm import LlmClient
from app.teacher_copilot.models.clients.ocr import OcrClient
from app.teacher_copilot.services.submission_service import SubmissionService

# 阶段名(与 contracts/grading-api.md 一致)
STAGE_QUEUED = "QUEUED"
STAGE_OCR = "OCR"
STAGE_PARSING = "PARSING"
STAGE_GRADING = "GRADING"
STAGE_ASSEMBLING = "ASSEMBLING_RESULT"
STAGE_COMPLETED = "COMPLETED"

STAGE_LABELS = {
    STAGE_OCR: "正在识别手写答案",
    STAGE_PARSING: "正在解析学生作答",
    STAGE_GRADING: "正在批改",
    STAGE_ASSEMBLING: "正在生成批改结果",
}


async def run_grading_workflow(submission_id: str) -> None:
    """后台异步执行一次完整 Grading Workflow(失败 → FAILED + 事件)。"""
    # 阶段日志(宪法 X):每阶段开始/结束各记一条,便于监控与排查
    logger.info("[%s] workflow 开始", submission_id)
    llm = LlmClient()
    ocr = OcrClient()
    t0 = time.time()
    try:
        async with SubmissionService() as sub_svc:
            sub = await sub_svc.get(submission_id)
        logger.info("[%s] 读取提交完成(耗时 %.1fs)", submission_id, time.time() - t0)
        await _set_stage(sub_id=submission_id, status="RUNNING", stage=STAGE_OCR)

        # 1) OCR(保存 OCRResult 证据)
        t_ocr = time.time()
        logger.info("[%s] OCR 请求开始, image_url=%s", submission_id, sub.image_url)
        # 幂等:若已存在 OCRResult(如注入/上次重跑),复用不重复识别;否则真实 OCR
        existing_ocr = await _get_ocr(submission_id)
        if existing_ocr is not None:
            ocr_result = {
                "md_results": existing_ocr.md_results or "",
                "layout_details": existing_ocr.layout_details or [],
            }
            logger.info("[%s] 复用已有 OCRResult(跳过 OCR, blocks=%d)",
                        submission_id, len(ocr_result["layout_details"]))
        else:
            # 本地测试用 file:// 路径:剥离前缀走 base64;真 URL(http/https)直接传给 SDK
            local_path = sub.image_url[7:] if sub.image_url.startswith("file://") else sub.image_url
            ocr_result = await ocr.recognize(
                local_path,
                image_url=sub.image_url if sub.image_url.startswith("http") else None,
            )
            logger.info("[%s] OCR 完成(耗时 %.1fs, blocks=%d)", submission_id,
                        time.time() - t_ocr, len(ocr_result.get("layout_details", [])))
            await _persist_ocr(submission_id, ocr_result)

        # 读取题目业务属性(确定性路由,不再让模型识别学科/难度)
        question = await _load_question(sub.question_id)
        logger.info("[%s] 题目加载完成: subject=%s question_type=%s difficulty=%s",
                    submission_id, question.subject, question.question_type, question.difficulty)
        await _set_stage(sub_id=submission_id, status="RUNNING", stage=STAGE_PARSING)

        # 拼装 OCR Block(按 index 升序)
        blocks = await _build_ocr_blocks(submission_id)
        logger.info("[%s] OCR Block 拼装完成: %d 个", submission_id, len(blocks))

        # 2) 批改路由
        await _set_stage(sub_id=submission_id, status="RUNNING", stage=STAGE_GRADING)
        taxonomy = TaxonomyValidator()
        async with taxonomy:
            kp_taxonomy = await _load_kp_keys(question.subject)
            err_taxonomy = await _load_err_codes(question.subject)
        logger.info("[%s] Taxonomy 加载完成: kp=%d err=%d", submission_id,
                    len(kp_taxonomy), len(err_taxonomy))

        if question.subject == "math":
            t_grad = time.time()
            logger.info("[%s] 数学批改调用开始", submission_id)
            raw = await run_math_grading(
                llm=llm, question={"content": question.content, "max_score": question.max_score},
                ocr_blocks=blocks, kp_taxonomy=kp_taxonomy, err_taxonomy=err_taxonomy,
            )
            logger.info("[%s] 数学批改完成(耗时 %.1fs)", submission_id, time.time() - t_grad)
            # 校验步骤分证据 Block 只引用真实 block
            await _validate_block_refs(raw, blocks)
            assembled = GradingResultAssembler.assemble_math(
                raw, subject="math", question_type=question.question_type,
                difficulty=question.difficulty,
            )
        else:
            t_grad = time.time()
            logger.info("[%s] 英语两阶段批改调用开始", submission_id)
            essay_text = _blocks_to_text(blocks)
            raw = await run_english_grading(
                llm=llm, question={"content": question.content},
                essay_text=essay_text, kp_taxonomy=kp_taxonomy, err_taxonomy=err_taxonomy,
            )
            logger.info("[%s] 英语批改完成(耗时 %.1fs)", submission_id, time.time() - t_grad)
            assembled = GradingResultAssembler.assemble_english(raw, subject="english", question_type=question.question_type)

        # 3) Taxonomy 校验并补齐 name/type
        # 诊断缺失时传空对象(而非在组装器补默认空诊断),让校验器的必需字段判定
        # 报出准确的"缺少必需字段",而不是被默认值掩盖成"没有知识点/错误"(008 FR-002)
        async with TaxonomyValidator() as validator:
            assembled["diagnosis"] = await validator.validate_diagnosis(
                subject=question.subject, diagnosis=assembled.get("diagnosis") or {}
            )
        logger.info("[%s] Taxonomy 校验完成: kp=%d err=%d", submission_id,
                    len(assembled["diagnosis"].get("knowledge_points", [])),
                    len(assembled["diagnosis"].get("errors", [])))

        # 4) 组装结果
        await _set_stage(sub_id=submission_id, status="RUNNING", stage=STAGE_ASSEMBLING)
        await _persist_grading_result(submission_id, question, assembled)
        logger.info("[%s] GradingResult 持久化完成, 得分 %s/%s", submission_id,
                    assembled["score"]["earned"], assembled["score"]["max"])

        # 5) 完成
        await _set_stage(sub_id=submission_id, status="SUCCEEDED", stage=STAGE_COMPLETED)
        await publish_grading_event("grading.completed", submission_id=submission_id, stage=STAGE_COMPLETED)
        logger.info("[%s] workflow 完成, 总耗时 %.1fs", submission_id, time.time() - t0)
    except Exception as exc:  # pragma: no cover - 失败路径统一处理
        from app.teacher_copilot.errors import TcError

        code = exc.code if isinstance(exc, TcError) else "GRADING_MODEL_FAILED"
        logger.exception("[%s] workflow 失败: code=%s (耗时 %.1fs)", submission_id, code, time.time() - t0)
        await _fail(submission_id, code, str(exc))
        await publish_grading_event("grading.stage.failed", submission_id=submission_id, stage=STAGE_GRADING, error_code=code, message=str(exc))


# ============ 帮助函数 ============

async def _set_stage(sub_id: str, status: str, stage: str) -> None:
    """更新状态 + 发布阶段事件(先落库,再推送)。"""
    async with SubmissionService() as svc:
        await svc.set_stage(sub_id, status, stage)
    label = STAGE_LABELS.get(stage)
    await publish_grading_event(
        "grading.stage.started" if stage != STAGE_COMPLETED else "grading.completed",
        submission_id=sub_id, stage=stage, label=label,
    )


async def _fail(sub_id: str, code: str, message: str) -> None:
    async with SubmissionService() as svc:
        await svc.set_failed(sub_id, code, message)


async def _load_question(question_id: str) -> Question:
    async with get_session() as session:
        q = await session.scalar(select(Question).where(Question.question_id == question_id))
        if q is None:
            raise RuntimeError(f"题目 {question_id} 不存在")
        return q


async def _get_ocr(submission_id: str) -> OcrResult | None:
    """读取已存在的 OCRResult(幂等复用)。"""
    async with get_session() as session:
        return await session.scalar(
            select(OcrResult).where(OcrResult.submission_id == submission_id)
        )


async def _persist_ocr(submission_id: str, ocr_result: dict) -> None:
    """持久化 OCRResult(核心证据,md_results + layout_details JSON)。"""
    async with get_session() as session:
        session.add(OcrResult(
            ocr_result_id=f"ocr_{submission_id}",
            submission_id=submission_id,
            model="glm-ocr",
            status="SUCCEEDED",
            md_results=ocr_result.get("md_results", ""),
            layout_details=ocr_result.get("layout_details", []),
        ))
        await session.commit()


async def _build_ocr_blocks(submission_id: str) -> list[dict]:
    """读取 OCRResult.layout_details 并按 index 升序(保持书写顺序)。"""
    async with get_session() as session:
        row = await session.scalar(select(OcrResult).where(OcrResult.submission_id == submission_id))
    if row is None or not row.layout_details:
        return []
    return sorted(row.layout_details, key=lambda b: b["index"])


async def _load_kp_keys(subject: str) -> list[str]:
    from app.teacher_copilot.db.models.taxonomy import KnowledgePoint

    async with get_session() as session:
        rows = await session.scalars(
            select(KnowledgePoint.key).where(
                KnowledgePoint.subject == subject, KnowledgePoint.level == 2
            )
        )
        return list(rows)


async def _load_err_codes(subject: str) -> list[str]:
    from app.teacher_copilot.db.models.taxonomy import ErrorType

    async with get_session() as session:
        rows = await session.scalars(
            select(ErrorType.code).where(ErrorType.subject == subject, ErrorType.level == 2)
        )
        return list(rows)


def _blocks_to_text(blocks: list[dict]) -> str:
    """OCR Block 拼装为稳定文本(英语作文输入)。"""
    return "\n\n".join(f"[Block {b['index']} | {b['label']}]\n{b['content']}" for b in blocks)


async def _validate_block_refs(raw: dict, blocks: list[dict]) -> None:
    """校验 error_block_ids/evidence_block_ids 指向真实存在的 Block。"""
    valid = {b["index"] for b in blocks}
    for step in raw.get("steps", []):
        for ref in step.get("error_block_ids", []) + step.get("evidence_block_ids", []):
            if ref not in valid:
                from app.teacher_copilot.errors import GradingOutputInvalid

                raise GradingOutputInvalid(f"Block {ref} 不存在于当前 OCR 结果")


async def _persist_grading_result(submission_id: str, question: Question, assembled: dict) -> None:
    """写入当前有效 GradingResult(含诊断子表)。"""
    gid = f"gr_{submission_id}"
    async with get_session() as session:
        session.add(GradingResult(
            grading_result_id=gid, submission_id=submission_id,
            subject=question.subject, question_type=question.question_type,
            difficulty=question.difficulty,
            score_earned=assembled["score"]["earned"], score_max=assembled["score"]["max"],
            score_rate=assembled["score"]["rate"],
            feedback=assembled["feedback"],
            math_detail=assembled["math_detail"],
            english_essay_detail=assembled["english_essay_detail"],
            execution_meta=assembled["execution_meta"],
        ))
        for kp in assembled["diagnosis"].get("knowledge_points", []):
            session.add(GradingResultKnowledgePoint(
                grading_result_id=gid, knowledge_point_key=kp["key"], name=kp.get("name"),
                raw_name=kp.get("raw_name", ""), performance=kp.get("performance", "partial"),
                evidence=kp.get("evidence"),
            ))
        for err in assembled["diagnosis"].get("errors", []):
            session.add(GradingResultError(
                grading_result_id=gid, error_code=err["code"], type_name=err.get("type"),
                raw_type=err.get("raw_type", ""), knowledge_point_key=err.get("knowledge_point_key", ""),
                description=err.get("description"), evidence=err.get("evidence"),
            ))
        await session.commit()


def schedule_grading(submission_id: str) -> asyncio.Task:
    """以 asyncio.create_task 方式后台执行批改(轻量异步,不引入任务队列)。"""
    return asyncio.create_task(run_grading_workflow(submission_id))
