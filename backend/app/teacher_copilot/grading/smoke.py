"""端到端冒烟:完整 Grading Workflow(真实 LLM + 注入 OCR blocks;数学批改)。

说明(宪法 X 可观察):全程结构化日志(stderr)+ 关键点 print(flush),
每阶段记录耗时。本脚本聚焦"Workflow 编排 + 数学批改 + 持久化"链路:
- OCR 环节用注入的 blocks(真实 glm-ocr 需公网可达图片 URL,本地 127.0.0.1
  智谱平台不可达;OCR 单点已在早前用公网 URL 单独验证过 36 blocks)
- 数学批改用真实 DeepSeek anthropic v1/messages
用法: python -m app.teacher_copilot.grading.smoke  (需在 backend 下,source .env)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time

from sqlalchemy import select

from app.teacher_copilot.config.settings import get_config

# 配置日志(宪法 X:stderr 输出,不依赖 stdout 缓冲)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

# 注入的 OCR blocks(模拟手写解题过程,index 升序保持书写顺序)
MOCK_BLOCKS = [
    {"index": 1, "label": "text", "content": "设 x 为未知数", "bbox2d": [0, 0, 100, 40], "width": 100, "height": 600},
    {"index": 2, "label": "formula", "content": "$$ 2x + 4 = 8 $$", "bbox2d": [0, 40, 100, 80], "width": 100, "height": 600},
    {"index": 3, "label": "text", "content": "移项得", "bbox2d": [0, 80, 100, 120], "width": 100, "height": 600},
    {"index": 4, "label": "formula", "content": "$$ 2x = 8 - 4 = 4 $$", "bbox2d": [0, 120, 100, 160], "width": 100, "height": 600},
    {"index": 5, "label": "formula", "content": "$$ x = 2 $$", "bbox2d": [0, 160, 100, 200], "width": 100, "height": 600},
]


async def main() -> None:
    from app.teacher_copilot.db.engine import create_all, dispose_db, get_session, init_db
    from app.teacher_copilot.db.models.grading import GradingResult, OcrResult, Submission
    from app.teacher_copilot.db.seed.demo import seed_demo
    from app.teacher_copilot.db.seed.question_bank import seed_question_bank
    from app.teacher_copilot.db.seed.taxonomy import seed_taxonomy
    from app.teacher_copilot.grading.workflow import run_grading_workflow

    cfg = get_config()
    t0 = time.time()
    await init_db("sqlite+aiosqlite:///tc-data/smoke2.db")
    await create_all()
    await seed_taxonomy()
    await seed_question_bank()
    await seed_demo()
    print(f"[{time.time()-t0:.0f}s] DB 初始化+种子就绪", flush=True)

    async with get_session() as s:
        from sqlalchemy import delete

        from app.teacher_copilot.db.models.grading import (
            GradingResultError, GradingResultKnowledgePoint,
        )

        old = await s.scalar(select(Submission).where(Submission.submission_id == "sub_smoke1"))
        if old is not None:
            gr = await s.scalar(select(GradingResult).where(GradingResult.submission_id == "sub_smoke1"))
            if gr is not None:
                await s.execute(delete(GradingResultKnowledgePoint).where(
                    GradingResultKnowledgePoint.grading_result_id == gr.grading_result_id))
                await s.execute(delete(GradingResultError).where(
                    GradingResultError.grading_result_id == gr.grading_result_id))
                await s.execute(delete(GradingResult).where(
                    GradingResult.submission_id == "sub_smoke1"))
            await s.execute(delete(OcrResult).where(OcrResult.submission_id == "sub_smoke1"))
            await s.execute(delete(Submission).where(Submission.submission_id == "sub_smoke1"))
            await s.commit()
        s.add(Submission(
            submission_id="sub_smoke1", student_id="stu_003",
            question_id="q001", homework_id="hw_004",
            image_url="tc-data/test_math.jpg",  # 业务资产 URL(本稿聚焦 workflow 编排)
            status="PENDING", current_stage="QUEUED",
        ))
        # 注入 OCR blocks(绕过网络 OCR,聚焦 math 批改+持久化)
        s.add(OcrResult(
            ocr_result_id="ocr_sub_smoke1", submission_id="sub_smoke1",
            model="glm-ocr", status="SUCCEEDED",
            md_results="", layout_details=MOCK_BLOCKS,
        ))
        await s.commit()
    print(f"[{time.time()-t0:.0f}s] 提交+OCR 就绪,启动 workflow...", flush=True)

    await run_grading_workflow("sub_smoke1")
    print(f"[{time.time()-t0:.0f}s] workflow 返回", flush=True)

    async with get_session() as s:
        sub = await s.scalar(select(Submission).where(Submission.submission_id == "sub_smoke1"))
        gr = await s.scalar(select(GradingResult).where(GradingResult.submission_id == "sub_smoke1"))
        print(f"submission 状态: {sub.status} / {sub.current_stage}", flush=True)
        if gr:
            print(f"GradingResult: {gr.score_earned}/{gr.score_max} rate={gr.score_rate}", flush=True)
            print(f"math_detail steps: {len(gr.math_detail.get('steps', [])) if gr.math_detail else 0}", flush=True)
        else:
            print("!! 未生成 GradingResult", flush=True)

    await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
